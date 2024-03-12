# exec-cmd

## cmd

A [maubot](https://github.com/maubot/maubot) that executes predefined shell commands.

### Setup

Instructions to run the bot in [standalone](https://docs.mau.fi/maubot/usage/standalone.html) mode.

Install dependencies and create a local user:

```bash
apt install python3-pip python3-setuptools python3-wheel python3-venv
useradd -r -d /opt/maubot -s /usr/sbin/nologin maubot
mkdir /opt/maubot
chown -R maubot:maubot /opt/maubot
su - maubot -s /bin/bash
```

Install maubot as maubot system user in a venv:

```bash
python3 -m venv env
source env/bin/activate
pip install --upgrade pip setuptools wheel
pip install --upgrade maubot[all]
```

Clone and setup the maubot plugin:

```bash
git clone https://gitlab.phys.ethz.ch/isgphys/maubot-exec-cmd.git git
ln -s git/maubot.yaml
ln -s git/exec_cmd
cp standalone-example-config.yaml config.yaml
```

Generate an `access_token` and `device_id` (login) using the
[client-server api](https://spec.matrix.org/latest/client-server-api/#post_matrixclientv3login)
with a cli http tool such as [httpie](https://httpie.io/):

```bash
http POST 'https://example.com/_matrix/client/v3/login' <<<'{"identifier":{"type":"m.id.user","user":"botusername"},"initial_device_display_name":"Standalone Bot","password":"ilovebananas","type":"m.login.password"}'
```

Invite the bot user to your room and note the `<roomid_or_alias>`.

Manually join the bot user to the room using the
[client-server api](https://spec.matrix.org/latest/client-server-api/#post_matrixclientv3joinroomidoralias):

```bash
http POST 'https://example.com/_matrix/client/v3/join/<roomid_or_alias>' Authorization:"Bearer <access_token>"
```

### Configuration

Configure the required bot user credentials: `id`, `homeserver`, `access_token` and `device_id`.

It is recommended to leave `user.autojoin` on `false` and use a manual join as shown above.

The command prefix can be configured with:

```yaml
prefix_cmd: 'cmd'
```

The list of Matrix user IDs who are allowed to execute predefined shell commands:

```yaml
whitelist_cmd:
- '@user:example.com'
```

The `commands` dictionary holds all predefined commands.
The keys represent the command names that can be sent to the bot.
For multi word bot commands `_` must be used as delimiter instead of spaces (` `).

```yaml
commands:
    ps: ps -ef | grep maubot
    device_off: echo powering off
    device_start: |
        echo device power on
        sleep 5
        echo device is starting
        sleep 5
        echo device started
```

### Usage

Start the bot:

```bash
python -m maubot.standalone
```

Available bot commands with the above:

```yaml
!cmd                # lists available commands
!cmd ps
!cmd device off
!cmd device start
```


## exec
A [maubot](https://github.com/maubot/maubot) that executes code.
exec is updated to be compatible with python 3.8+.

### Usage
The bot is triggered by a specific message prefix (defaults to `!exec`) and
executes the code in the first code block.

<pre>
!exec
```python
print("Hello, World!")
```
</pre>

Standard input can be added with another code block that has `stdin` as the
language:

<pre>
!exec
```python
print(f"Hello, {input()}")
```

```stdin
maubot
```
</pre>

When the bot executes the code, it'll reply immediately and then update the
output using edits until the command finishes. After it finishes, the reply
will be edited to contain the return values.

If running in userbot mode, the bot will edit your original message instead of
making a new reply message.

Currently, the bot supports `python` and `shell` as languages.
