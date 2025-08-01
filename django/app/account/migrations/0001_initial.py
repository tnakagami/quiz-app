# Generated by Django 5.2.2 on 2025-06-12 11:52

import account.models
import django.db.models.deletion
import utils.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(help_text='Required. 128 characters allowing only Unicode characters, in addition to @, ., -, and _.', max_length=128, unique=True, verbose_name='email address')),
                ('code', models.CharField(default=account.models._get_code, max_length=22, verbose_name='code')),
                ('screen_name', models.CharField(blank=True, help_text='Optional. 128 characters or fewer.', max_length=128, verbose_name='screen name')),
                ('password', models.CharField(help_text='It must contain at least four types which are an alphabet (uppercase/lowercase), a number, and a symbol.', max_length=128, verbose_name='password')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site or not.', verbose_name='staff status')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates whether the user is a superuser or not.', verbose_name='superuser status')),
                ('is_active', models.BooleanField(default=False, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('role', models.IntegerField(choices=[(1, 'Manager'), (2, 'Creator'), (3, 'Guest')], default=3, verbose_name='Role')),
                ('friends', models.ManyToManyField(blank=True, related_name='my_friends', to=settings.AUTH_USER_MODEL, verbose_name='My friends')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'abstract': False,
            },
            managers=[
                ('objects', account.models.CustomUserManager()),
            ],
        ),
        migrations.CreateModel(
            name='IndividualGroup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Required. 128 characters or fewer.', max_length=128, verbose_name='group name')),
                ('members', models.ManyToManyField(related_name='group_members', to=settings.AUTH_USER_MODEL, verbose_name='Group members')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='group_owners', to=settings.AUTH_USER_MODEL, verbose_name='Group owner')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='RoleApproval',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('requested_date', models.DateTimeField(default=utils.models.get_current_time, verbose_name='Requested time')),
                ('is_completed', models.BooleanField(default=False, help_text="Designates whether this user’s role has already been approved or not.", verbose_name='Approval status')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approvals', to=settings.AUTH_USER_MODEL, verbose_name='Candidate for approval')),
            ],
            options={
                'ordering': ('-requested_date',),
            },
        ),
    ]
