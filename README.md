# Society Management development access

The application keeps its two existing portals separate. Start each one in its own terminal from this folder.

Terminal 1 (User Portal):

```bash
python run_user.py
```

Local User Portal: `http://127.0.0.1:5000`

Terminal 2 (Admin Portal):

```bash
python run_admin.py
```

Local Admin Portal: `http://127.0.0.1:5001/admin/login`

To share them for development, authenticate ngrok separately (once per machine) and run one tunnel per portal:

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

Terminal 3 (User Portal tunnel):

```bash
ngrok http 5000
```

Terminal 4 (Admin Portal tunnel):

```bash
ngrok http 5001
```

Use the HTTPS URL printed by the port 5000 tunnel for residents. Use the distinct HTTPS URL printed by the port 5001 tunnel for administrators (append `/admin/login` if needed). Do not put either temporary URL or the ngrok auth token in source code or `.env`.

## Session and security notes

Internal links, redirects, and API requests use Flask-generated paths or relative URLs, so they remain on the current portal when accessed via ngrok. Session cookies retain the existing `SameSite=Lax` setting; production mode retains `SESSION_COOKIE_SECURE=True`. No CSRF or host-validation settings were weakened for tunnel access.
