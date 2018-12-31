from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.reverse import reverse

from mayan.apps.acls.models import AccessControlList
from mayan.apps.documents.models import Document

from .models import Tag
from .permissions import permission_tag_attach


class TagSerializer(serializers.HyperlinkedModelSerializer):
    documents_url = serializers.HyperlinkedIdentityField(
        lookup_field='pk', lookup_url_kwarg='tag_pk',
        view_name='rest_api:tag-document-list'
    )
    documents_count = serializers.SerializerMethodField()

    class Meta:
        extra_kwargs = {
            'url': {
                'lookup_field': 'pk', 'lookup_url_kwarg': 'tag_pk',
                'view_name': 'rest_api:tag-detail'
            }
        }
        fields = (
            'color', 'documents_count', 'documents_url', 'id', 'label', 'url'
        )
        model = Tag

    def get_documents_count(self, instance):
        return instance.documents.count()


class WritableTagSerializer(serializers.ModelSerializer):
    documents_pk_list = serializers.CharField(
        help_text=_(
            'Comma separated list of document primary keys to which this tag '
            'will be attached.'
        ), required=False
    )

    class Meta:
        fields = (
            'color', 'documents_pk_list', 'id', 'label',
        )
        model = Tag

    def _add_documents(self, documents_pk_list, instance):
        instance.documents.add(
            *Document.objects.filter(pk__in=documents_pk_list.split(','))
        )

    def create(self, validated_data):
        documents_pk_list = validated_data.pop('documents_pk_list', '')

        instance = super(WritableTagSerializer, self).create(validated_data)

        if documents_pk_list:
            self._add_documents(
                documents_pk_list=documents_pk_list, instance=instance
            )

        return instance

    def update(self, instance, validated_data):
        documents_pk_list = validated_data.pop('documents_pk_list', '')

        instance = super(WritableTagSerializer, self).update(
            instance, validated_data
        )

        if documents_pk_list:
            instance.documents.clear()
            self._add_documents(
                documents_pk_list=documents_pk_list, instance=instance
            )

        return instance


class DocumentTagSerializer(TagSerializer):
    document_tag_url = serializers.SerializerMethodField(
        help_text=_(
            'API URL pointing to a tag in relation to the document '
            'attached to it. This URL is different than the canonical '
            'tag URL.'
        )
    )
    tag_pk = serializers.IntegerField(
        help_text=_('Primary key of the tag to be added.'), write_only=True
    )

    class Meta(TagSerializer.Meta):
        fields = TagSerializer.Meta.fields + ('document_tag_url', 'tag_pk')
        read_only_fields = TagSerializer.Meta.fields + ('document_tag_url',)

    def get_document_tag_url(self, instance):
        return reverse(
            viewname='rest_api:document-tag-detail', kwargs={
                'document_pk': self.context['document'].pk,
                'tag_pk': instance.pk
            }, request=self.context['request'], format=self.context['format']
        )

    def create(self, validated_data):
        queryset = AccessControlList.objects.filter_by_access(
            permission=permission_tag_attach, queryset=Tag.objects.all(),
            user=self.context['request'].user
        )
        tag = get_object_or_404(queryset=queryset, pk=validated_data['tag_pk'])
        tag.documents.add(self.context['document'])
        return tag
