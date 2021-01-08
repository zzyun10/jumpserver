import jinja2
import yaml

from django.db import models
from django.utils.translation import ugettext_lazy as _, get_language

from orgs.mixins.models import OrgModelMixin
from common.mixins import CommonModelMixin
from .. import const


class Application(CommonModelMixin, OrgModelMixin):
    name = models.CharField(max_length=128, verbose_name=_('Name'))
    category = models.CharField(
        max_length=16, choices=const.ApplicationCategoryChoices.choices, verbose_name=_('Category')
    )
    type = models.CharField(
        max_length=16, choices=const.ApplicationTypeChoices.choices, verbose_name=_('Type')
    )
    domain = models.ForeignKey(
        'assets.Domain', null=True, blank=True, related_name='applications',
        on_delete=models.SET_NULL, verbose_name=_("Domain"),
    )
    attrs = models.JSONField(default=dict, verbose_name=_('Attrs'))
    comment = models.TextField(
        max_length=128, default='', blank=True, verbose_name=_('Comment')
    )

    class Meta:
        unique_together = [('org_id', 'name')]
        ordering = ('name',)

    def __str__(self):
        category_display = self.get_category_display()
        type_display = self.get_type_display()
        return f'{self.name}({type_display})[{category_display}]'

    @property
    def category_remote_app(self):
        return self.category == const.ApplicationCategoryChoices.remote_app.value


class RemoteAppType(CommonModelMixin):
    name = models.CharField(max_length=128)
    label = models.CharField(max_length=128)
    description = models.TextField()
    author = models.CharField(max_length=128)
    company = models.CharField(max_length=128, blank=True, null=True)
    license = models.CharField(max_length=128, blank=True, null=True)
    tags = models.JSONField()
    path = models.CharField()

    @property
    def params(self):
        return {}

    @property
    def i18n(self):
        return {}

    def generate_params_serializer(self):
        from common.drf.serializers import DefinitionSerializerFactory

        cls_name = 'RemoteApp{}Serializer'.format(self.name.title())
        lang = get_language()
        serializer = DefinitionSerializerFactory.generate_serializer_by_param(
            cls_name, self.params, i18n_data=self.i18n, lang=lang
        )
        return serializer

    @classmethod
    def load_from_tarball(cls, path):
        pass

    def __str__(self):
        return f'{self.name}({self.display_name})'
