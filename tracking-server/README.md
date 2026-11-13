# Tracking server

Records each player's progress and hands out the prize form link once every quest is done.

## Run

```sh
pip install -r requirements.txt
export HS_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python main.py
```

## Settings

| Variable | Required | Meaning |
|---|---|---|
| `HS_JWT_SECRET` | yes | Signs the prize key. Keep it out of the repository and use a new one each year. |
| `HS_REDEEM_FORM_URL` | no | The prize form, with `{token}` where the key is prefilled. Defaults to this year's form. |

To check a key someone submitted, decode it with the same secret, for example
`jwt.decode(key, os.environ["HS_JWT_SECRET"], algorithms=["HS256"])`.
