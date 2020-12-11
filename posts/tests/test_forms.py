import shutil
import tempfile

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings
from django.urls import reverse

from posts.models import Follow, Post
from posts.tests.test_settings import TestSettings


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(dir=settings.BASE_DIR))
class PostCreateFormTest(TestSettings):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_create_new_post(self):
        """Новый пост создаётся успешно"""
        posts_count = Post.objects.count()
        small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x02\x00"
            b"\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xFF\xFF\xFF\x21\xF9\x04\x00\x00"
            b"\x00\x00\x00\x2C\x00\x00\x00\x00"
            b"\x02\x00\x01\x00\x00\x02\x02\x0C"
            b"\x0A\x00\x3B"
        )
        uploaded = SimpleUploadedFile(
            name="small.gif", content=small_gif, content_type="image/gif"
        )
        form_data = {
            "text": "Test.",
            "group": self.group.id,
            "image": uploaded,
        }
        response = self.authorized_client.post(
            reverse("new_post"), data=form_data, follow=True
        )
        post = Post.objects.first()
        self.assertRedirects(response, reverse("index"))
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertEqual(post.text, form_data["text"])
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.group.id, form_data["group"])
        self.assertNotEqual(post.group.id, self.group2)
        self.assertIsNotNone(response.context["post"].image)

    def test_edit_post(self):
        """Пост редактируется"""
        form_data = {
            "text": "modified text",
            "group": self.group.id,
        }
        self.authorized_client.post(
            reverse("post_edit", args=[self.user, self.post.id]),
            data=form_data,
            follow=True,
        )
        post = Post.objects.last()
        self.assertEqual(post.text, form_data["text"])
        self.assertEqual(post.author, self.user)
        self.assertEqual(post.group.id, form_data["group"])

    def test_new_post_created_on_page_followers(self):
        """Записи фолловеров.

        Новая запись пользователя появляется в ленте тех,
        кто на него подписан."""
        self.follow = Follow.objects.create(
            user=self.user,
            author=self.user2,
        )
        posts_count = Post.objects.count()
        form_data = {
            "text": "Новый пост",
            "group": self.group.id,
            "author": self.user2,
        }
        self.authorized_client2.post(
            reverse("new_post"),
            data=form_data,
            follow=True,
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        first_post = Post.objects.first()
        response = self.authorized_client.get(reverse("follow_index"))
        post = response.context["page"].object_list[0]
        self.assertEqual(post, first_post)

    def test_new_post_dont_show_on_unfollowers_page(self):
        """Записи фолловеров.

        Новая запись пользователя не появляется в ленте тех,
        кто НЕ подписан на него"""
        self.follow = Follow.objects.create(
            user=self.user,
            author=self.user2,
        )
        posts_count = Post.objects.count()
        form_data = {
            "text": "Новый пост",
            "group": self.group.id,
            "author": self.user2,
        }
        self.authorized_client2.post(
            reverse("new_post"),
            data=form_data,
            follow=True,
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        response = self.authorized_client2.get(reverse("follow_index"))
        posts = response.context["page"].object_list
        self.assertEqual(len(posts), 0)

    def test_cache(self):
        """Тест кэширования индекса"""
        client = self.authorized_client
        response = client.get(reverse("index"))
        content = response.content
        Post.objects.all().delete()
        response = client.get(reverse("index"))
        self.assertEqual(content, response.content, "Кеширование не работает")
        cache.clear()
        response = client.get(reverse("index"))
        self.assertNotEqual(
            content, response.content, "Кеширование неисправно"
        )
