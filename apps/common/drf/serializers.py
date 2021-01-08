import yaml
import jinja2

from rest_framework import serializers
from rest_framework.serializers import Serializer
from rest_framework.serializers import ModelSerializer
from rest_framework_bulk.serializers import BulkListSerializer

from common.mixins import BulkListSerializerMixin
from django.utils.functional import cached_property
from rest_framework.utils.serializer_helpers import BindingDict
from common.mixins.serializers import BulkSerializerMixin

__all__ = [
    'MethodSerializer', 'EmptySerializer', 'BulkModelSerializer',
    'AdaptedBulkListSerializer', 'CeleryTaskSerializer',
    'DefinitionSerializerFactory'
]


# MethodSerializer
# ----------------


class MethodSerializer(serializers.Serializer):

    def __init__(self, method_name=None, **kwargs):
        self.method_name = method_name
        super().__init__(**kwargs)

    def bind(self, field_name, parent):
        if self.method_name is None:
            method_name = 'get_{field_name}_serializer'.format(field_name=field_name)
            self.method_name = method_name

        super().bind(field_name, parent)

    @cached_property
    def serializer(self) -> serializers.Serializer:
        method = getattr(self.parent, self.method_name)
        return method()

    def get_fields(self):
        return self.serializer.get_fields()

    @cached_property
    def fields(self):
        """
        重写此方法因为在 BindingDict 中要设置每一个 field 的 parent 为 `serializer`,
        这样在调用 field.parent 时, 才会达到预期的结果，
        比如: serializers.SerializerMethodField
        """
        fields = BindingDict(self.serializer)
        for key, value in self.get_fields().items():
            fields[key] = value
        return fields


# Other Serializer
# ----------------


class EmptySerializer(Serializer):
    pass


class BulkModelSerializer(BulkSerializerMixin, ModelSerializer):
    pass


class AdaptedBulkListSerializer(BulkListSerializerMixin, BulkListSerializer):
    pass


class CeleryTaskSerializer(serializers.Serializer):
    task = serializers.CharField(read_only=True)


class DefinitionSerializerFactory:
    """
    使用定义的 参数来生成 serializer

    - name: url
      label: "{{ 'URL' | i18n }}"
      type: string
      default: http://www.jumpserver.org
      required: false
      help_text: "{{ 'URL chrome to open' | i18n }}"

    - name: username
      label: "{{ 'Username' | i18n }}"
      type: string
      required: false
      placeholder: "{{ 'Username' | i18n }}"
      help_text: "{{ 'Username for login' | i18n }}"

    - name: password
      label: "{{ 'Password' | i18n }}"
      type: string
      required: false
    """
    type_serializer_field_mapper = {
        'string': serializers.CharField,
        'integer': serializers.IntegerField,
        'text': serializers.CharField,
        'password': serializers.CharField,
    }

    @classmethod
    def generate_param_field(cls, cleaned_param):
        name = cleaned_param.pop('name', 'notset')
        tp = cleaned_param.pop('type', 'unknown')
        field_cls = cls.type_serializer_field_mapper.get(tp)
        if not field_cls:
            raise TypeError('Field type not found: {}: {}'.format(name, tp))
        return field_cls(**cleaned_param)

    @classmethod
    def clean_param(cls, param):
        valid_keys = ['name', 'label', 'type', 'default', 'required', 'help_text']
        cleaned_param = {}
        for k, v in param.items():
            if k not in valid_keys:
                continue
            cleaned_param[k] = v
        # name 和 type, 两个字段必填
        if not {'name', 'type'} & set(cleaned_param.keys()):
            cleaned_param = {}
            return cleaned_param

        tp = cleaned_param['type']
        if tp not in cls.type_serializer_field_mapper.keys():
            cleaned_param = {}
            return cleaned_param

        if cleaned_param.get("default", None) is not None and cleaned_param.get("required"):
            cleaned_param['initial'] = cleaned_param.pop('default')

        if tp == 'string':
            if not cleaned_param.get('max_length'):
                cleaned_param['max_length'] = 1024
        elif tp == 'password':
            cleaned_param['write_only'] = True
        return cleaned_param

    @classmethod
    def clean_params(cls, params, i18n_data=None, lang='zh'):
        if not isinstance(i18n_data, dict):
            i18n_data = {}
        params = yaml.dump(params, sort_keys=False, default_flow_style=False).replace("''", '"')
        env = jinja2.Environment()

        def i18n(value):
            code = 'zh'
            if lang.startswith('zh'):
                code = 'zh'
            elif lang.startswith('en'):
                code = 'en'
            return i18n_data.get(code, {}).get(value, value)

        env.filters['i18n'] = i18n
        template = env.from_string(params)
        params = yaml.safe_load(template.render())
        cleaned_params = []
        for p in params:
            param = cls.clean_param(p)
            if param:
                cleaned_params.append(param)
        return cleaned_params

    @classmethod
    def generate_serializer_by_param(cls, cls_name, params, i18n_data=None, lang='cn'):
        fields = {}
        cleaned_params = cls.clean_params(params, i18n_data=i18n_data, lang=lang)
        for param in cleaned_params:
            name = param['name']
            field = cls.generate_param_field(param)
            fields[name] = field
        return type(cls_name, (Serializer,), fields)()
