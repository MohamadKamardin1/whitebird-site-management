from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import apps.core.files


class Migration(migrations.Migration):
    dependencies = [("site_management", "0026_remuneration_payment_audit_fields")]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation_type", models.CharField(choices=[("direct", "Direct"), ("group", "Group")], db_index=True, max_length=16)),
                ("title", models.CharField(blank=True, default="", max_length=160)),
                ("direct_key", models.CharField(blank=True, default=None, max_length=64, null=True, unique=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_message_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-last_message_at", "-updated_at"]},
        ),
        migrations.CreateModel(
            name="ConversationMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("joined_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("left_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_read_at", models.DateTimeField(blank=True, null=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="site_management.conversation")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="message_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["conversation_id", "user__email"]},
        ),
        migrations.CreateModel(
            name="ConversationMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("body", models.TextField(blank=True, default="", max_length=5000)),
                ("delivered_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="messages", to="site_management.conversation")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_conversation_messages", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.CreateModel(
            name="ConversationMessageAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("file", models.FileField(help_text="Privately stored file; never exposed via a public URL.", max_length=500, storage=apps.core.files.PrivateMediaStorage(), upload_to="private/%Y/%m/")),
                ("original_filename", models.CharField(blank=True, default="", max_length=255)),
                ("content_type", models.CharField(blank=True, default="", max_length=127)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("attachment_type", models.CharField(choices=[("document", "Document"), ("pdf", "PDF"), ("image", "Image"), ("voice", "Voice")], db_index=True, max_length=16)),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="site_management.conversationmessage")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.AddIndex(model_name="conversation", index=models.Index(fields=["conversation_type", "is_active", "last_message_at"], name="site_manage_convers_47f152_idx")),
        migrations.AddIndex(model_name="conversationmembership", index=models.Index(fields=["user", "is_active", "conversation"], name="site_manage_user_id_e0c6ca_idx")),
        migrations.AddConstraint(model_name="conversationmembership", constraint=models.UniqueConstraint(fields=("conversation", "user"), name="uniq_conversation_member")),
        migrations.AddIndex(model_name="conversationmessage", index=models.Index(fields=["conversation", "created_at"], name="site_manage_convers_11fd01_idx")),
        migrations.AddIndex(model_name="conversationmessageattachment", index=models.Index(fields=["message", "attachment_type"], name="site_manage_message_d8ae8d_idx")),
    ]
