from enum import IntEnum


class Perms(IntEnum):

    administrator = 1
    manage_guild = 2
    view_audit_log = 3
    ban_members = 4
    kick_members = 5
    manage_roles = 6
    manage_channels = 7
    manage_nicknames = 8
    manage_emojis = 9
    manage_messages = 10
    manage_webhooks = 11
    deafen_members = 12
    move_members = 13
    mute_members = 14
    mention_everyone = 15
    create_instant_invite = 16
    send_tts_messages = 17
    embed_links = 18
    attach_files = 19
    change_nickname = 20
    external_emojis = 21
    connect = 22
    speak = 23
    read_message_history = 24
    read_messages = 25
    send_messages = 26
    use_voice_activation = 27
    add_reactions = 28
