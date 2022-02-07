# exec
A [maubot](https://github.com/maubot/maubot) that executes code.
exec is updated to be compatible with python 3.8+.

## Usage
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


## Contributors

  <a href="https://github.com/YingzhouLi/exec/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=YingzhouLi/exec" />
  </a>

  Made with [contrib.rocks](https://contrib.rocks).
