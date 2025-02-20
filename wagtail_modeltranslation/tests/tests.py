from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import HttpRequest
from django.test import TestCase, override_settings
from django.test.client import RequestFactory
from django.utils import translation
from wagtail.core.models import Page, Site
from wagtail.snippets.views.snippets import get_snippet_edit_handler
from wagtail_modeltranslation.tests import models

from .util import page_factory

request_factory = RequestFactory()


class WagtailModeltranslationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(WagtailModeltranslationTest, cls).setUpClass()
        Page.objects.all().delete()

    def test_page_fields(self):
        fields = dir(models.PatchTestPage())

        # Check if Page fields are being created
        self.assertIn('title_en', fields)
        self.assertIn('title_de', fields)
        self.assertIn('slug_en', fields)
        self.assertIn('slug_de', fields)
        self.assertIn('seo_title_en', fields)
        self.assertIn('seo_title_de', fields)
        self.assertIn('search_description_en', fields)
        self.assertIn('search_description_de', fields)
        self.assertIn('url_path_en', fields)
        self.assertIn('url_path_de', fields)

        # Check if subclass fields are being created
        self.assertIn('description_en', fields)
        self.assertIn('description_de', fields)

    def test_snippet_fields(self):
        fields = dir(models.PatchTestSnippet())

        self.assertIn('name', fields)
        self.assertIn('name_en', fields)
        self.assertIn('name_de', fields)

    def check_fieldpanel_patching(self, panels, name='name'):
        # Check if there is one panel per language
        self.assertEquals(len(panels), 2)

        # Validate if the created panels are instances of FieldPanel
        from wagtail.admin.edit_handlers import FieldPanel

        self.assertIsInstance(panels[0], FieldPanel)
        self.assertIsInstance(panels[1], FieldPanel)

        # Check if both field names were correctly created
        fields = [panel.field_name for panel in panels]
        self.assertListEqual([name + '_de', name + '_en'], fields)

    def check_imagechooserpanel_patching(self, panels, name='image'):
        # Check if there is one panel per language
        self.assertEquals(len(panels), 2)

        from wagtail.images.edit_handlers import ImageChooserPanel
        self.assertIsInstance(panels[0], ImageChooserPanel)
        self.assertIsInstance(panels[1], ImageChooserPanel)

        # Check if both field names were correctly created
        fields = [panel.field_name for panel in panels]
        self.assertListEqual([name + '_de', name + '_en'], fields)

    def check_fieldrowpanel_patching(self, panels, child_name='other_name'):
        # Check if the fieldrowpanel still exists
        self.assertEqual(len(panels), 1)

        from wagtail.admin.edit_handlers import FieldRowPanel
        self.assertIsInstance(panels[0], FieldRowPanel)

        # Check if the children were correctly patched using the fieldpanel test
        children_panels = panels[0].children

        self.check_fieldpanel_patching(panels=children_panels, name=child_name)

    def check_streamfieldpanel_patching(self, panels):
        # Check if there is one panel per language
        self.assertEquals(len(panels), 2)

        from wagtail.admin.edit_handlers import StreamFieldPanel
        self.assertIsInstance(panels[0], StreamFieldPanel)
        self.assertIsInstance(panels[1], StreamFieldPanel)

        # Check if both field names were correctly created
        fields = [panel.field_name for panel in panels]
        self.assertListEqual(['body_de', 'body_en'], fields)

        # Fetch one of the streamfield panels to see if the block was correctly created
        child_block = list(models.StreamFieldPanelPage.body_en.field.stream_block.child_blocks.items())

        self.assertEquals(len(child_block), 1)

        from wagtail.core.blocks import CharBlock
        self.assertEquals(child_block[0][0], 'text')
        self.assertIsInstance(child_block[0][1], CharBlock)

        # Original and Default language StreamFields are required
        self.assertFalse(models.StreamFieldPanelPage.body.field.blank)
        self.assertTrue(models.StreamFieldPanelPage.body.field.stream_block.required)
        self.assertFalse(models.StreamFieldPanelPage.body_de.field.blank)
        self.assertTrue(models.StreamFieldPanelPage.body_de.field.stream_block.required)

        # Translated StreamField is optional
        self.assertTrue(models.StreamFieldPanelPage.body_en.field.blank)
        self.assertFalse(models.StreamFieldPanelPage.body_en.field.stream_block.required)

    def check_multipanel_patching(self, panels):
        # There are three multifield panels, one for each of the available
        # children panels
        self.assertEquals(len(panels), 3)

        from wagtail.admin.edit_handlers import MultiFieldPanel
        self.assertIsInstance(panels[0], MultiFieldPanel)
        self.assertIsInstance(panels[1], MultiFieldPanel)
        self.assertIsInstance(panels[2], MultiFieldPanel)

        fieldpanel = panels[0].children
        imagechooser = panels[1].children
        fieldrow = panels[2].children

        self.check_fieldpanel_patching(panels=fieldpanel)
        self.check_imagechooserpanel_patching(panels=imagechooser)
        self.check_fieldrowpanel_patching(panels=fieldrow)

    def check_inlinepanel_patching(self, panels):
        # The inline panel has all the available combination of children panels making
        # a grand total of 8 panels
        self.assertEqual(len(panels), 8)

        # The first 2 panels are fieldpanels, the following 2 are imagechooserpanels,
        # next is a fieldrowpanel and finally there are 3 multifieldpanels
        self.check_fieldpanel_patching(panels=panels[0:2], name='field_name')
        self.check_imagechooserpanel_patching(panels=panels[2:4], name='image_chooser')
        self.check_fieldrowpanel_patching(panels=panels[4:5], child_name='fieldrow_name')
        self.check_multipanel_patching(panels=panels[5:8])

    def test_page_patching(self):
        self.check_fieldpanel_patching(panels=models.FieldPanelPage.content_panels)
        self.check_imagechooserpanel_patching(panels=models.ImageChooserPanelPage.content_panels)
        self.check_fieldrowpanel_patching(panels=models.FieldRowPanelPage.content_panels)
        self.check_streamfieldpanel_patching(panels=models.StreamFieldPanelPage.content_panels)
        self.check_multipanel_patching(panels=models.MultiFieldPanelPage.content_panels)

        # In spite of the model being the InlinePanelPage the panels are patch on the related model
        # which is the PageInlineModel
        self.check_inlinepanel_patching(panels=models.PageInlineModel.panels)

    def test_snippet_patching(self):
        self.check_fieldpanel_patching(panels=models.FieldPanelSnippet.panels)
        self.check_panels_patching(models.FieldPanelSnippet, ['name_de', 'name_en'])

        self.check_imagechooserpanel_patching(panels=models.ImageChooserPanelSnippet.panels)
        self.check_fieldrowpanel_patching(panels=models.FieldRowPanelSnippet.panels)
        self.check_streamfieldpanel_patching(panels=models.StreamFieldPanelSnippet.panels)
        self.check_multipanel_patching(panels=models.MultiFieldPanelSnippet.panels)

        # In spite of the model being the InlinePanelSnippet the panels are patch on the related model
        # which is the SnippetInlineModel
        self.check_inlinepanel_patching(panels=models.SnippetInlineModel.panels)

        # Case we don't define panels on snippet
        self.check_panels_patching(models.PatchTestSnippetNoPanels, ['name_de', 'name_en'])

    def check_panels_patching(self, model, model_fields):
        patched_edit_handler = get_snippet_edit_handler(model)

        form = patched_edit_handler.get_form_class()

        self.assertEqual(model_fields, list(form.base_fields.keys()))

    def test_page_form(self):
        """
        In this test we use the InlinePanelPage model because it has all the possible "patchable" fields
        so if the created form has all fields the the form was correctly patched
        """

        page_edit_handler = models.InlinePanelPage.get_edit_handler()

        form = page_edit_handler.get_form_class()

        page_base_fields = ['slug_de', 'slug_en', 'seo_title_de', 'seo_title_en', 'search_description_de',
                            'search_description_en', u'show_in_menus', u'go_live_at', u'expire_at']

        form_fields = list(form.base_fields.keys())
        # exclude field injected in form:
        # https://github.com/wagtail/wagtail/blob/main/wagtail/admin/forms/pages.py#L131
        if 'comment_notifications' in form_fields:
            form_fields.remove('comment_notifications')
        self.assertEqual(page_base_fields, form_fields)

        inline_model_fields = ['field_name_de', 'field_name_en', 'image_chooser_de', 'image_chooser_en',
                               'fieldrow_name_de', 'fieldrow_name_en', 'name_de', 'name_en', 'image_de', 'image_en',
                               'other_name_de', 'other_name_en']

        related_formset_form = form.formsets['related_page_model'].form
        self.assertEqual(inline_model_fields, list(related_formset_form.base_fields.keys()))

    def test_snippet_form(self):
        """
        In this test we use the InlinePanelSnippet model because it has all the possible "patchable" fields
        so if the created form has all fields the the form was correctly patched
        """
        snippet_edit_handler = get_snippet_edit_handler(models.InlinePanelSnippet)

        form = snippet_edit_handler.get_form_class()

        inline_model_fields = ['field_name_de', 'field_name_en', 'image_chooser_de', 'image_chooser_en',
                               'fieldrow_name_de', 'fieldrow_name_en', 'name_de', 'name_en', 'image_de', 'image_en',
                               'other_name_de', 'other_name_en']

        related_formset_form = form.formsets['related_snippet_model'].form

        self.assertEqual(inline_model_fields, list(related_formset_form.base_fields.keys()))

    def test_duplicate_slug(self):
        from wagtail.core.models import Site

        # Create a test Site with a root page
        root = models.TestRootPage(title='title', depth=1, path='0001', slug_en='slug_en', slug_de='slug_de')
        root.save()

        site = Site(root_page=root)
        site.save()

        # Add children to the root
        root.add_child(
            instance=models.TestSlugPage1(title='child1', slug_de='child', slug_en='child-en', depth=2, path='00010001')
        )

        child2 = root.add_child(
            instance=models.TestSlugPage2(title='child2', slug_de='child-2', slug_en='child2-en', depth=2,
                                          path='00010002')
        )

        # Clean should work fine as the two slugs are different
        child2.clean()

        # Make the slug equal to test if the duplicate is detected
        child2.slug_de = 'child'
        self.assertRaises(ValidationError, child2.clean)
        child2.slug_de = 'child-2'

        # Make the translated slug equal to test if the duplicate is detected
        child2.slug_en = 'child-en'
        self.assertRaises(ValidationError, child2.clean)

    @override_settings(LANGUAGE_CODE='de')
    def test_slugurl_trans(self):
        """
        Assert tag slugurl_trans is immune to user's current language
        """
        from wagtail_modeltranslation.templatetags.wagtail_modeltranslation import \
            slugurl_trans
        site_pages = {
            'model': models.TestRootPage,
            'kwargs': {'title_de': 'root slugurl', },
            'children': {
                'child': {
                    'model': models.TestSlugPage1,
                    'kwargs': {'title': 'child slugurl', 'slug': 'child-slugurl', 'slug_en': 'child-slugurl-en'},
                    'children': {},
                },
            },
        }
        site = page_factory.create_page_tree(site_pages)

        request_mock = request_factory.get('/')
        setattr(request_mock, 'site', site)
        context = {'request': request_mock}

        self.assertEqual(slugurl_trans(context, 'root-slugurl'), '/de/')
        self.assertEqual(slugurl_trans(context, 'child-slugurl'), '/de/child-slugurl/')
        self.assertEqual(slugurl_trans(context, 'child-slugurl-en', 'en'), '/de/child-slugurl/')

        translation.activate('en')

        self.assertEqual(slugurl_trans(context, 'root-slugurl'), '/en/')
        self.assertEqual(slugurl_trans(context, 'child-slugurl'), '/en/child-slugurl-en/')
        self.assertEqual(slugurl_trans(context, 'child-slugurl-en', 'en'), '/en/child-slugurl-en/')

    @override_settings(LANGUAGE_CODE='de')
    def test_relative_url(self):
        # Create a test Site with a root page
        root = models.TestRootPage(title_de='title slugurl', depth=1, path='0004',
                                   slug_en='title_slugurl_en', slug_de='title_slugurl_de')
        root.save()
        site = Site(root_page=root)
        site.save()

        # Add children to the root
        child = root.add_child(
            instance=models.TestSlugPage1(
                title_de='child1 slugurl',
                slug_de='child-slugurl-de',
                slug_en='child-slugurl-en',
                depth=2, path='00040001'
            )
        )
        child.save_revision().publish()

        url_1_de = child.relative_url(site)
        self.assertEqual(
            url_1_de,
            '/de/child-slugurl-de/',
            'When using the default language, slugurl produces the wrong url.'
        )

        translation.activate('en')

        url_1_en = child.relative_url(site)
        self.assertEqual(url_1_en, '/en/child-slugurl-en/',
                         'When using non-default language, slugurl produces the wrong url.')

        # Add children using non-default language
        child2 = root.add_child(
            instance=models.TestSlugPage2(
                title='child2 slugurl',
                title_de='child2 slugurl DE',
                slug_de='child2-slugurl-de',
                slug_en='child2-slugurl-en',
                depth=2,
                path='00040002'
            )
        )
        child2.save_revision().publish()

        url_2_en = child2.relative_url(site)
        self.assertEqual(url_2_en, '/en/child2-slugurl-en/',
                         'When using non-default language, slugurl produces the wrong url.')

        translation.activate('de')

        url_2_de = child2.relative_url(site)
        self.assertEqual(url_2_de, '/de/child2-slugurl-de/',
                         'When using non-default language, slugurl produces the wrong url.')

    def test_searchfield_patching(self):
        # Check if the search fields have the original field plus the translated ones
        expected_fields = ['title', 'title_de', 'title_en', 'description', 'description_de', 'description_en']

        model_search_fields = [searchfield.field_name for searchfield in models.PatchTestPage.search_fields]

        self.assertCountEqual(expected_fields, model_search_fields)

    def test_streamfield_fallback(self):
        body_text = '[{"value": "Some text", "type": "text"}]'
        page = models.StreamFieldPanelPage(title='Streamfield Fallback', slug='streamfield_fallback',
                                           depth=1, path='0005', body=body_text)
        page.save()

        self.assertEqual(str(page.body), '<div class="block-text">Some text</div>')

        translation.activate('en')

        self.assertEqual(str(page.body), '<div class="block-text">Some text</div>',
                         'page.body did not fallback to original language.')

    @override_settings(LANGUAGE_CODE='de')
    def test_set_url_path(self):
        """
        Assert translation URL Paths are correctly set in page and descendants for a slug change and
        page move operations
        """
        from wagtail.core.models import Site

        # Create a test Site with a root page
        root = models.TestRootPage.objects.create(title='url paths', depth=1, path='0006', slug='url-path-slug')

        Site.objects.create(root_page=root)

        # Add children to the root
        child = root.add_child(
            instance=models.TestSlugPage1(
                title_de='child',
                title_en='child',
                slug_de='child',
                slug_en='child',
                depth=2,
                path='00060001'
            )
        )
        child.save()

        # Add grandchildren to the root
        grandchild = child.add_child(
            instance=models.TestSlugPage1(
                title_de='grandchild',
                title_en='grandchild',
                slug_de='grandchild',
                slug_en='grandchild',
                depth=2,
                path='000600010001')
        )
        grandchild.save()

        # check everything is as expected
        self.assertEqual(root.url_path_de, '/')
        self.assertEqual(root.url_path_en, '/')
        self.assertEqual(child.url_path_de, '/child/')
        self.assertEqual(child.url_path_en, '/child/')
        self.assertEqual(grandchild.url_path_de, '/child/grandchild/')
        self.assertEqual(grandchild.url_path_en, '/child/grandchild/')

        # PAGE SLUG CHANGE
        grandchild.slug_de = 'grandchild_de'
        grandchild.save()

        self.assertEqual(grandchild.url_path_de, '/child/grandchild_de/')
        self.assertEqual(grandchild.url_path_en, '/child/grandchild/')

        grandchild.slug_en = 'grandchild_en'
        grandchild.save()

        self.assertEqual(grandchild.url_path_de, '/child/grandchild_de/')
        self.assertEqual(grandchild.url_path_en, '/child/grandchild_en/')

        # Children url paths should update when parent changes
        child.slug_en = 'child_en'
        child.save()

        self.assertEqual(child.url_path_de, '/child/')
        self.assertEqual(child.url_path_en, '/child_en/')

        # Retrieve grandchild from DB:
        grandchild_new = models.TestSlugPage1.objects.get(id=grandchild.id)
        self.assertEqual(grandchild_new.url_path_en, '/child_en/grandchild_en/')
        self.assertEqual(grandchild_new.url_path_de, '/child/grandchild_de/')

        # Add 2nd child to the root
        child2 = root.add_child(
            instance=models.TestSlugPage1(
                title_de='child2',
                title_en='child2',
                slug_de='child2',
                slug_en='child2',
                depth=2,
                path='00060002'
            )
        )
        child2.save()

        self.assertEqual(child2.url_path_de, '/child2/')
        self.assertEqual(child2.url_path_en, '/child2/')

        # Add grandchildren
        grandchild2 = child2.add_child(
            instance=models.TestSlugPage1(
                title_de='grandchild2',
                title_en='grandchild2',
                slug_de='grandchild2',
                slug_en='grandchild2',
                depth=3,
                path='000600020001'
            )
        )
        grandchild2.save()

        self.assertEqual(grandchild2.url_path_de, '/child2/grandchild2/')
        self.assertEqual(grandchild2.url_path_en, '/child2/grandchild2/')

        # PAGE MOVE
        child2.move(child, pos='last-child')

        # re-fetch child2 to confirm db fields have been updated
        child2 = models.TestSlugPage1.objects.get(id=child2.id)

        self.assertEqual(child2.depth, 3)
        self.assertEqual(child2.get_parent().id, child.id)
        self.assertEqual(child2.url_path_de, '/child/child2/')
        self.assertEqual(child2.url_path_en, '/child_en/child2/')

        # children of child2 should also have been updated
        grandchild2 = child2.get_children().get(slug='grandchild2').specific
        self.assertEqual(grandchild2.depth, 4)
        self.assertEqual(grandchild2.url_path_de, '/child/child2/grandchild2/')
        self.assertEqual(grandchild2.url_path_en, '/child_en/child2/grandchild2/')

    def test_set_url_path_non_translated_descendants(self):
        """
        Assert set_url_path works correctly when a Page with untranslated children
        has its translated slug changed.
        """
        site_pages = {
            'model': models.TestRootPage,
            'kwargs': {'title': 'root untranslated', },
            'children': {
                'child': {
                    'model': models.TestSlugPage1,
                    'kwargs': {'title': 'child untranslated'},
                    'children': {
                        'grandchild1': {
                            'model': models.TestSlugPage1,
                            'kwargs': {'title': 'grandchild1 untranslated'},
                            'children': {
                                'grandgrandchild': {
                                    'model': models.TestSlugPage1,
                                    'kwargs': {'title': 'grandgrandchild untranslated'},
                                },
                            },
                        },
                        'grandchild2': {
                            'model': models.TestSlugPage2,
                            'kwargs': {'title': 'grandchild2 untranslated'},
                        },
                    },
                },
            },
        }
        page_factory.create_page_tree(site_pages)

        # Revert grandchild1 and grandgrandchild url_path_en to their initial untranslated states
        # to simulate pages that haven't been translated yet
        models.TestSlugPage1.objects.filter(slug_de__in=['grandchild1-untranslated', 'grandgrandchild-untranslated'])\
            .rewrite(False).update(slug_en=None, url_path_en=None)

        # re-fetch to pick up latest from DB
        grandchild1 = models.TestSlugPage1.objects.get(slug_de='grandchild1-untranslated')
        self.assertEqual(grandchild1.url_path_de, '/root-untranslated/child-untranslated/grandchild1-untranslated/')
        self.assertEqual(grandchild1.slug_en, None)
        self.assertEqual(grandchild1.url_path_en, None)
        grandgrandchild = models.TestSlugPage1.objects.get(slug_de='grandgrandchild-untranslated')
        self.assertEqual(grandgrandchild.url_path_de,
                         '/root-untranslated/child-untranslated/grandchild1-untranslated/grandgrandchild-untranslated/')
        self.assertEqual(grandgrandchild.slug_en, None)
        self.assertEqual(grandgrandchild.url_path_en, None)

        translation.activate('en')

        child = site_pages['children']['child']['instance']
        child.slug_en = 'child-translated'
        child.save()

        self.assertEqual(child.url_path_de, '/root-untranslated/child-untranslated/')
        self.assertEqual(child.url_path_en, '/root-untranslated/child-translated/')

        grandchild1 = models.TestSlugPage1.objects.get(slug_de='grandchild1-untranslated')
        self.assertEqual(grandchild1.url_path_de, '/root-untranslated/child-untranslated/grandchild1-untranslated/')
        self.assertEqual(grandchild1.url_path_en, '/root-untranslated/child-translated/grandchild1-untranslated/')

        grandgrandchild = models.TestSlugPage1.objects.get(slug_de='grandgrandchild-untranslated')
        self.assertEqual(grandgrandchild.url_path_de,
                         '/root-untranslated/child-untranslated/grandchild1-untranslated/grandgrandchild-untranslated/')
        self.assertEqual(grandgrandchild.url_path_en,
                         '/root-untranslated/child-translated/grandchild1-untranslated/grandgrandchild-untranslated/')

    def test_fetch_translation_records(self):
        """
        Assert that saved translation fields are retrieved correctly
        See: https://github.com/infoportugal/wagtail-modeltranslation/issues/103#issuecomment-352006610
        """
        page = models.StreamFieldPanelPage.objects.create(
            title_de='Fetch DE', title_en='Fetch EN', slug_de='fetch_de', slug_en='fetch_en',
            body_de=[('text', 'fetch de')], body_en=[('text', 'fetch en')], depth=1, path='0007')
        page.save()

        page_db = models.StreamFieldPanelPage.objects.get(id=page.id)

        self.assertEqual(page_db.title_de, 'Fetch DE')
        self.assertEqual(page_db.slug_de, 'fetch_de')
        self.assertEqual(str(page_db.body_de), '<div class="block-text">fetch de</div>')
        self.assertEqual(page_db.title_en, 'Fetch EN')
        self.assertEqual(page_db.slug_en, 'fetch_en')
        self.assertEqual(str(page_db.body_en), '<div class="block-text">fetch en</div>')

    def check_route_request(self, root_page, components, expected_page):
        # site = Site.objects.get(is_default_site=True)
        request = HttpRequest()
        # request.META['HTTP_HOST'] = site.hostname
        # request.META['SERVER_PORT'] = site.port

        request.path = '/' + '/'.join(components) + '/'
        (found_page, args, kwargs) = root_page.route(request, components)
        self.assertEqual(found_page, expected_page)

    @override_settings(LANGUAGE_CODE='de')
    def test_request_routing(self):
        """
        Assert .route works for translated slugs
        """
        site_pages = {
            'model': models.TestRootPage,
            'kwargs': {
                'title_de': 'root routing',
                'slug_de': 'root-routing'
            },
            'children': {
                'child1': {
                    'model': models.TestSlugPage1,
                    'kwargs': {
                        'title_de': 'child1 routing',
                        'slug_de': 'routing-de-01',
                        'slug_en': 'routing-en-01'
                    },
                    'children': {
                        'grandchild1': {
                            'model': models.TestSlugPage1,
                            'kwargs': {
                                'title_de': 'grandchild1 routing',
                                'slug_de': 'routing-de-0101',
                                'slug_en': 'routing-en-0101'
                            },
                        },
                    },
                },
                'child2': {
                    'model': models.TestSlugPage1,
                    'kwargs': {
                        'title_de': 'child2 routing',
                        'slug_de': 'routing-de-02'
                    },
                    'children': {
                        'grandchild1': {
                            'model': models.TestSlugPage1,
                            'kwargs': {
                                'title_de': 'grandchild1 routing',
                                'slug_de': 'routing-de-0201'
                            },
                        },
                    },
                },
                'routable_page': {
                    'model': models.RoutablePageTest,
                    'kwargs': {
                        'title_de': 'Routable Page',
                        'slug_de': 'routing-de-03',
                        'slug_en': 'routing-en-03',
                        'live': True
                    },
                    'children': {
                        'grandchild1': {
                            'model': models.TestSlugPage1,
                            'kwargs': {
                                'title_de': 'grandchild1 routing',
                                'slug_de': 'routing-de-0301',
                                'slug_en': 'routing-en-0301'
                            },
                        },
                    },
                },
            },
        }
        page_factory.create_page_tree(site_pages)

        root_page = site_pages['instance']
        page_0101 = site_pages['children']['child1']['children']['grandchild1']['instance']
        page_0201 = site_pages['children']['child2']['children']['grandchild1']['instance']
        page_0301 = site_pages['children']['routable_page']['children']['grandchild1']['instance']

        self.check_route_request(root_page, ['routing-de-01', 'routing-de-0101'], page_0101)
        self.check_route_request(root_page, ['routing-de-02', 'routing-de-0201'], page_0201)

        # routable page test
        routable_page = site_pages['children']['routable_page']['instance']
        view, args, kwargs = routable_page.resolve_subpage('/archive/year/2014/')
        self.assertEqual(view, routable_page.archive_by_year)
        self.assertEqual(args, ('2014',))
        self.assertEqual(kwargs, {})
        self.check_route_request(root_page, ['routing-de-03', 'routing-de-0301'], page_0301)

        translation.activate('en')

        # assert translated slugs fetch the correct page
        self.check_route_request(root_page, ['routing-en-01', 'routing-en-0101'], page_0101)
        # in the absence of translated slugs assert the default ones work
        self.check_route_request(root_page, ['routing-de-02', 'routing-de-0201'], page_0201)

        view, args, kwargs = routable_page.resolve_subpage('/archive/year/2014/')
        self.assertEqual(view, routable_page.archive_by_year)
        self.assertEqual(args, ('2014',))
        self.assertEqual(kwargs, {})
        self.check_route_request(root_page, ['routing-en-03', 'routing-en-0301'], page_0301)

    def test_get_url_parts(self):
        site_pages = {
            'model': models.TestRootPage,
            'kwargs': {'title': 'root URL parts', },
            'children': {
                'child1': {
                    'model': models.TestSlugPage1,
                    'kwargs': {'title': 'child1 URL parts', 'slug_de': 'url-parts-de-01', 'slug_en': 'url-parts-en-01'},
                },
                'child2': {
                    'model': models.TestSlugPage1,
                    'kwargs': {'title': 'child2 URL parts', 'slug': 'url-parts-de-02'},
                },
            },
        }
        site = page_factory.create_page_tree(site_pages)

        root_page = site_pages['instance']
        page_01 = site_pages['children']['child1']['instance']
        page_02 = site_pages['children']['child2']['instance']

        self.assertEqual(root_page.relative_url(site), '/de/')
        self.assertEqual(page_01.relative_url(site), '/de/url-parts-de-01/')
        self.assertEqual(page_02.relative_url(site), '/de/url-parts-de-02/')

        translation.activate('en')

        self.assertEqual(root_page.relative_url(site), '/en/')
        self.assertEqual(page_01.relative_url(site), '/en/url-parts-en-01/')
        self.assertEqual(page_02.relative_url(site), '/en/url-parts-de-02/')

    @override_settings(LANGUAGE_CODE='de')
    def test_url(self):
        site_pages = {
            'model': models.TestRootPage,
            'kwargs': {'title': 'root URL', },
            'children': {
                'child1': {
                    'model': models.TestSlugPage1,
                    'kwargs': {'title': 'child1 URL', 'slug_de': 'url-de-01', 'slug_en': 'url-en-01'},
                },
                'child2': {
                    'model': models.TestSlugPage2,
                    'kwargs': {'title': 'child2 URL', 'slug_de': 'url-de-02'},
                },
            },
        }
        page_factory.create_page_tree(site_pages)

        root_page = site_pages['instance']
        page_01 = site_pages['children']['child1']['instance']
        page_02 = site_pages['children']['child2']['instance']

        self.assertEqual(root_page.url, '/de/')
        self.assertEqual(page_01.url, '/de/url-de-01/')
        self.assertEqual(page_02.url, '/de/url-de-02/')

        translation.activate('en')

        self.assertEqual(root_page.url, '/en/')
        self.assertEqual(page_01.url, '/en/url-en-01/')
        self.assertEqual(page_02.url, '/en/url-de-02/')

    @override_settings(LANGUAGE_CODE='de')
    def test_root_page_slug(self):
        site_pages = {
            'model': models.TestRootPage,
            'kwargs': {
                'title': 'root URL',
                'slug_de': 'root-de',
                'slug_en': 'root-en'
            },
            'children': {
                'child1': {
                    'model': models.TestSlugPage1,
                    'kwargs': {
                        'title': 'child1 URL',
                        'slug_de': 'url-de-01',
                        'slug_en': 'url-en-01'
                    },
                },
                'child2': {
                    'model': models.TestSlugPage2,
                    'kwargs': {
                        'title': 'child2 URL',
                        'slug_de': 'url-de-02'
                    },
                },
                'child3': {
                    'model': models.TestSlugPage2,
                    'kwargs': {
                        'title': 'child3 URL',
                        'slug_de': 'url-de-03'
                    },
                },
            },
        }
        page_factory.create_page_tree(site_pages)
        site = Site.objects.get(is_default_site=True)
        request = HttpRequest()
        request.META['HTTP_HOST'] = site.hostname
        request.META['SERVER_PORT'] = site.port

        site_root_page = site_pages['instance']
        wagtail_page_01 = site_pages['children']['child1']['instance']
        wagtail_page_02 = site_pages['children']['child2']['instance']
        wagtail_page_03 = site_pages['children']['child3']['instance']
        self.assertEqual(wagtail_page_01.url, '/de/url-de-01/')
        self.assertEqual(wagtail_page_01.url_path, '/root-de/url-de-01/')
        self.assertEqual(wagtail_page_02.get_url(request=request), '/de/url-de-02/')  # with request

        translation.activate('en')

        self.assertEqual(wagtail_page_01.url, '/en/url-en-01/')
        self.assertEqual(wagtail_page_01.url_path, '/root-en/url-en-01/')
        self.assertEqual(wagtail_page_02.get_url(request=request), '/en/url-de-02/')

        translation.activate('de')

        # new request after changing language
        self.assertEqual(wagtail_page_03.url, '/de/url-de-03/')
        self.assertEqual(wagtail_page_01.get_url(request=request), '/de/url-de-01/')

        # URL should not be broken after updating the root_page (ensure the cache is evicted)
        self.assertEqual(wagtail_page_01.url, '/de/url-de-01/')
        site_root_page.slug = 'new-root-de'
        site_root_page.save()
        wagtail_page_01_new = site_root_page.get_children().get(id=wagtail_page_01.id)
        self.assertEqual(wagtail_page_01_new.url, '/de/url-de-01/')

    def test_set_translation_url_paths_command(self):
        """
        Assert set_translation_url_paths management command works correctly
        """
        site_pages = {
            'model': models.TestRootPage,
            'kwargs': {'title': 'root untranslated', },
            'children': {
                'child': {
                    'model': models.TestSlugPage1,
                    'kwargs': {'title': 'child untranslated'},
                    'children': {
                        'grandchild1': {
                            'model': models.TestSlugPage1,
                            'kwargs': {'title': 'grandchild1 untranslated'},
                            'children': {
                                'grandgrandchild': {
                                    'model': models.TestSlugPage1,
                                    'kwargs': {'title': 'grandgrandchild untranslated'},
                                },
                            },
                        },
                        'grandchild2': {
                            'model': models.TestSlugPage2,
                            'kwargs': {'title': 'grandchild2 untranslated'},
                        },
                    },
                },
                'child2': {
                    'model': models.TestSlugPage1,
                    'kwargs': {'title': 'child2 translated', 'slug_en': 'child2-translated-en'},
                    'children': {
                        'grandchild1': {
                            'model': models.TestSlugPage1,
                            'kwargs': {'title': 'grandchild1 translated', 'slug_en': 'grandchild1-translated-en'},
                            'children': {
                                'grandgrandchild': {
                                    'model': models.TestSlugPage1,
                                    'kwargs': {'title': 'grandgrandchild1 translated',
                                               'slug_en': 'grandgrandchild1-translated-en'},
                                },
                            },
                        },
                    },
                },
            },
        }
        page_factory.create_page_tree(site_pages)

        # Revert grandchild1 and grandgrandchild url_path_en to their initial untranslated states
        # to simulate pages that haven't been translated yet
        models.TestSlugPage1.objects.filter(slug_de__in=['grandchild1-untranslated', 'grandgrandchild-untranslated']) \
            .rewrite(False).update(slug_en=None, url_path_en=None)

        # re-fetch to pick up latest from DB
        grandchild1 = models.TestSlugPage1.objects.get(slug_de='grandchild1-untranslated')
        self.assertEqual(grandchild1.url_path_en, None)
        grandgrandchild = models.TestSlugPage1.objects.get(slug_de='grandgrandchild-untranslated')
        self.assertEqual(grandgrandchild.url_path_en, None)

        # change grandchild2 url_path to corrupt it in order to simulate Wagtail's 0.7 corruption bug:
        # http://docs.wagtail.io/en/latest/releases/0.8.html#corrupted-url-paths-may-need-fixing
        models.TestSlugPage2.objects.filter(
            slug_de__in=['grandchild2-untranslated']
        ).rewrite(False).update(url_path='corrupted', url_path_de='corrupted')

        grandchild2 = models.TestSlugPage2.objects.get(slug_de='grandchild2-untranslated')
        self.assertEqual(grandchild2.__dict__['url_path'], 'corrupted')

        call_command('set_translation_url_paths', verbosity=0)

        grandchild1 = models.TestSlugPage1.objects.get(slug_de='grandchild1-untranslated')
        self.assertEqual(grandchild1.url_path_de, '/root-untranslated/child-untranslated/grandchild1-untranslated/')
        self.assertEqual(grandchild1.url_path_en, '/root-untranslated/child-untranslated/grandchild1-untranslated/')
        grandgrandchild = models.TestSlugPage1.objects.get(slug_de='grandgrandchild-untranslated')
        self.assertEqual(grandgrandchild.url_path_de,
                         '/root-untranslated/child-untranslated/grandchild1-untranslated/grandgrandchild-untranslated/')
        self.assertEqual(grandgrandchild.url_path_en,
                         '/root-untranslated/child-untranslated/grandchild1-untranslated/grandgrandchild-untranslated/')
        grandchild2 = models.TestSlugPage2.objects.get(slug_de='grandchild2-untranslated')
        self.assertEqual(
            grandchild2.__dict__['url_path'],
            '/root-untranslated/child-untranslated/grandchild2-untranslated/'
        )
        self.assertEqual(grandchild2.url_path_de, '/root-untranslated/child-untranslated/grandchild2-untranslated/')
        self.assertEqual(grandchild2.url_path_en, '/root-untranslated/child-untranslated/grandchild2-untranslated/')

        grandgrandchild_translated = models.TestSlugPage1.objects.get(slug_de='grandgrandchild1-translated')
        self.assertEqual(
            grandgrandchild_translated.url_path_de,
            '/root-untranslated/child2-translated/grandchild1-translated/grandgrandchild1-translated/'
        )
        self.assertEqual(
            grandgrandchild_translated.url_path_en,
            '/root-untranslated/child2-translated-en/grandchild1-translated-en/grandgrandchild1-translated-en/'
        )
