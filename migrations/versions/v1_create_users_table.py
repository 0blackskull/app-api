"""Create complete database schema

Revision ID: v1
Revises: 
Create Date: 2024-01-01 00:00:00

Combined migration that creates the complete final database schema
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'v1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        
        # User data fields (consolidated from previous Profile model)
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("city_of_birth", sa.String(), nullable=True),
        sa.Column("current_residing_city", sa.String(), nullable=True),
        sa.Column("time_of_birth", sa.DateTime(), nullable=True),
        sa.Column("life_events_json", sa.Text(), nullable=True),
        sa.Column("is_past_fact_visible", sa.Boolean(), nullable=False, server_default='true'),
        
        # Subscription fields
        sa.Column("subscription_type", sa.String(), nullable=False, server_default="free"),
        sa.Column("subscription_status", sa.String(), nullable=False, server_default="inactive"),
        sa.Column("subscription_end_date", sa.DateTime(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="inactive"),
        sa.Column("credits", sa.Integer(), nullable=False, server_default='3'),
        sa.Column("has_unlimited_chat", sa.Boolean(), nullable=False, server_default='false'),
        
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username")
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Create chat_threads table
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Chat"),
        sa.Column("is_title_edited", sa.Boolean(), nullable=False, server_default='false'),
        sa.Column("auto_generated_title", sa.String(255), nullable=True),
        sa.Column("participants_json", sa.Text(), nullable=True),
        sa.Column("compatibility_type", sa.String(20), nullable=True),
        sa.Column("ashtakoota_raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_chat_threads_id"), "chat_threads", ["id"], unique=False)
    op.create_index(op.f("ix_chat_threads_user_id"), "chat_threads", ["user_id"], unique=False)
    op.create_index("ix_chat_threads_user_updated", "chat_threads", ["user_id", "updated_at"])

    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_messages_id"), "messages", ["id"], unique=False)
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)
    op.create_index(op.f("ix_messages_thread_id"), "messages", ["thread_id"], unique=False)

    # Create partners table
    op.create_table(
        "partners",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("city_of_birth", sa.String(), nullable=False),
        sa.Column("time_of_birth", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_partners_id"), "partners", ["id"], unique=False)
    op.create_index(op.f("ix_partners_user_id"), "partners", ["user_id"], unique=False)

    # Create compatibilities table
    op.create_table(
        "compatibilities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("partner_id", sa.String(), nullable=True),
        sa.Column("other_user_id", sa.String(), nullable=True),
        sa.Column("report_type", sa.String(20), nullable=False, server_default="love"),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["other_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint('user_id', 'partner_id', 'report_type', name='uq_user_partner_compatibility'),
        sa.UniqueConstraint('user_id', 'other_user_id', 'report_type', name='uq_user_other_user_compatibility')
    )

    # Create google_play_payments table
    op.create_table(
        "google_play_payments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("purchase_token", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("purchase_state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("consumption_state", sa.String(), nullable=False, server_default="0"),
        sa.Column("acknowledgment_state", sa.String(), nullable=False, server_default="not_acknowledged"),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default='false'),
        sa.Column("purchase_type", sa.String(), nullable=False, server_default="inapp"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_token")
    )
    op.create_index(op.f("ix_google_play_payments_user_id"), "google_play_payments", ["user_id"], unique=False)
    op.create_index(op.f("ix_google_play_payments_product_id"), "google_play_payments", ["product_id"], unique=False)
    op.create_index(op.f("ix_google_play_payments_purchase_token"), "google_play_payments", ["purchase_token"], unique=True)
    op.create_index(op.f("ix_google_play_payments_status"), "google_play_payments", ["status"], unique=False)
    op.create_index(op.f("ix_google_play_payments_purchase_state"), "google_play_payments", ["purchase_state"], unique=False)
    op.create_index(op.f("ix_google_play_payments_consumption_state"), "google_play_payments", ["consumption_state"], unique=False)
    op.create_index(op.f("ix_google_play_payments_acknowledgment_state"), "google_play_payments", ["acknowledgment_state"], unique=False)
    op.create_index(op.f("ix_google_play_payments_purchase_type"), "google_play_payments", ["purchase_type"], unique=False)

    # Create subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("purchase_token", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("purchase_state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("start_time", sa.Integer(), nullable=True),
        sa.Column("end_time", sa.Integer(), nullable=True),
        sa.Column("acknowledgment_state", sa.String(), nullable=False, server_default="not_acknowledged"),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default='false'),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_token")
    )
    op.create_index(op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_product_id"), "subscriptions", ["product_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_purchase_token"), "subscriptions", ["purchase_token"], unique=True)
    op.create_index(op.f("ix_subscriptions_status"), "subscriptions", ["status"], unique=False)
    op.create_index(op.f("ix_subscriptions_purchase_state"), "subscriptions", ["purchase_state"], unique=False)
    op.create_index(op.f("ix_subscriptions_acknowledgment_state"), "subscriptions", ["acknowledgment_state"], unique=False)

    # Create purchase_events table
    op.create_table(
        "purchase_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("purchase_token", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("product_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True, server_default="pending"),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id")
    )
    op.create_index(op.f("ix_purchase_events_id"), "purchase_events", ["id"], unique=False)
    op.create_index(op.f("ix_purchase_events_message_id"), "purchase_events", ["message_id"], unique=True)
    op.create_index(op.f("ix_purchase_events_purchase_token"), "purchase_events", ["purchase_token"], unique=False)
    op.create_index(op.f("ix_purchase_events_user_id"), "purchase_events", ["user_id"], unique=False)

    # Create friend_requests table
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("requester_id", sa.String(), nullable=False),
        sa.Column("recipient_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint('requester_id', 'recipient_id', name='unique_friend_request')
    )
    op.create_index(op.f("ix_friend_requests_id"), "friend_requests", ["id"], unique=False)
    op.create_index(op.f("ix_friend_requests_requester_id"), "friend_requests", ["requester_id"], unique=False)
    op.create_index(op.f("ix_friend_requests_recipient_id"), "friend_requests", ["recipient_id"], unique=False)

    # Create friendships table
    op.create_table(
        "friendships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user1_id", sa.String(), nullable=False),
        sa.Column("user2_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user1_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user2_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint('user1_id', 'user2_id', name='unique_friendship')
    )
    op.create_index(op.f("ix_friendships_id"), "friendships", ["id"], unique=False)
    op.create_index(op.f("ix_friendships_user1_id"), "friendships", ["user1_id"], unique=False)
    op.create_index(op.f("ix_friendships_user2_id"), "friendships", ["user2_id"], unique=False)

    # Create user_streaks table
    op.create_table(
        "user_streaks",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("last_active_local_date", sa.Date(), nullable=True),
        sa.Column("last_active_at_utc", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("user_id", name="uq_user_streaks_user_id")
    )

    # Create devices table
    op.create_table(
        "devices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("fcm_token", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("app_version", sa.String(), nullable=True),
        sa.Column("lang", sa.String(), nullable=True),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default='true'),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fcm_token", name="uq_devices_fcm_token")
    )
    op.create_index(op.f("ix_devices_user_id"), "devices", ["user_id"], unique=False)

    # Create rants table
    op.create_table(
        "rants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("therapist_response", sa.Text(), nullable=False),
        sa.Column("is_valid_rant", sa.Boolean(), nullable=False),
        sa.Column("rant_type", sa.String(50), nullable=False),
        sa.Column("emotional_tone", sa.String(100), nullable=False),
        sa.Column("validation_reasoning", sa.Text(), nullable=False),
        sa.Column("streak_updated", sa.Boolean(), nullable=False, server_default='false'),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(op.f("ix_rants_id"), "rants", ["id"], unique=False)
    op.create_index(op.f("ix_rants_user_id"), "rants", ["user_id"], unique=False)
    op.create_index(op.f("ix_rants_submitted_at"), "rants", ["submitted_at"], unique=False)


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table("rants")
    op.drop_table("devices")
    op.drop_table("user_streaks")
    op.drop_table("friendships")
    op.drop_table("friend_requests")
    op.drop_table("purchase_events")
    op.drop_table("subscriptions")
    op.drop_table("google_play_payments")
    op.drop_table("compatibilities")
    op.drop_table("partners")
    op.drop_table("messages")
    op.drop_table("chat_threads")
    op.drop_table("users") 