# Skapapp
# RFID-basert Skaplåssystem

Et komplett FastAPI-prosjekt for å administrere og overvåke et RFID-integrert garderobeskapssystem. Systemet tilbyr dynamisk og statisk skapreservasjon, rollebasert tilgangskontroll (admin/bruker), logging av skapbruk, statistikkvisning og databasebackup.

---

## Innhold

* [Funksjoner](#funksjoner)
* [Teknologi](#teknologi)
* [Katalogstruktur](#katalogstruktur)
* [Kjøreprosedyre](#kjøreprosedyre)
* [API-endepunkter](#api-endepunkter)
* [Statistikk](#statistikk)
* [Backup og Restore](#backup-og-restore)
* [Feilhåndtering](#feilhåndtering)
* [Videre utvikling](#videre-utvikling)

---

## Funksjoner

* **RFID-integrasjon**: Skanning av RFID-tagger for innlogging og skapbruk
* **Dynamiske og statiske skap**: Brukere kan reservere ledige skap, eller tilordnes faste
* **Admin-panel**: Opprettelse og sletting av garderoberom og skap
* **Logging**: Registrerer alle skapåpninger og -låsinger
* **Statistikk**: Oversikt over brukere, brukte skap, ledige skap og mer
* **Backup/Restore**: Eksport og import av databasen til/fra JSON
* **Asynkron opprydding**: Automatisk frigjøring av reserverte skap etter timeout

---

## Teknologi

* **Python 3.13**
* **FastAPI** - Backend-API
* **SQLite** - Lettvekts database
* **SQLAlchemy** - ORM
* **Jinja2** - Templating-motor for HTML
* **Uvicorn** - ASGI-server

---

## Katalogstruktur

```
.
├── main.py                     # Hovedapplikasjon (FastAPI)
├── database.py                # Databaseoppsett og backupfunksjoner
├── backend/
│   └── model/
│       ├── Locker.py
│       ├── LockerRoom.py
│       ├── LockerLog.py
│       ├── AdminUser.py
│       ├── StandardUser.py
│       ├── Statistic.py
│       └── ErrorHandler.py
├── static/                    # CSS / JS / bilder
├── templates/                 # HTML-filer for frontend
└── database.db                # SQLite databasefil
```

---

## Kjøreprosedyre

1. Installer avhengigheter:

```bash
pip install -r requirements.txt
```

2. Start applikasjonen:

```bash
uvicorn main:api --host localhost --port 8080 --reload
```

3. Åpne i nettleser: [http://localhost:8080](http://localhost:8080)

---

## API-endepunkter (utdrag)

### Brukerautentisering

* `POST /login` - Logg inn med passord
* `POST /admin_users/` - Opprett ny adminbruker

### RFID og reservasjon

* `POST /scan_rfid/` - Skann tag og hent ledige skap
* `PUT /lockers/reserve` - Reserver skap

### CRUD-operasjoner

* `POST /locker_rooms/{name}` - Opprett garderoberom
* `DELETE /lockers/{locker_id}` - Slett skap

### Midlertidige handlinger

* `PUT /lockers/temporary_unlock` - Midlertidig åpning
* `PUT /lockers/manual_release` - Manuell frigjøring

---

## Statistikk

* `GET /statistic/total_lockers` - Totalt antall skap
* `GET /statistic/occupied_lockers` - Antall brukte skap
* `GET /statistic/most_active_users` - Topp 10 aktive brukere
* `GET /statistic/recent_log_entries` - Siste 10 hendelser

---

## Backup og Restore

* `GET /admin/backup` - Last ned database som JSON
* `POST /admin/restore` - Gjenopprett database fra JSON

---

## Feilhåndtering

Feil logges automatisk til fil:

* Windows: `%USERPROFILE%/fastapi_logs/fastapi_errors.log`
* Linux/macOS: `/var/log/fastapi_errors.log`

Feil fanges og returneres som `HTTPException` med riktig statuskode.

---

## Videre utvikling

* [ ] JWT-basert autentisering
* [ ] Mer avansert frontend (f.eks. React eller Vue)
* [ ] Skapstatus i sanntid via WebSocket
* [ ] E-post/SMS-varsler
* [ ] Brukerhistorikkvisning i GUI
