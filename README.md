# RFID-basert garderobesystem for Sunnaas Sykehus

Dette prosjektet er en komplett løsning for administrasjon av låsbare skap ved hjelp av RFID-teknologi, utviklet som en del av en bacheloroppgave. Systemet kombinerer maskinvare og programvare for å tilby sikker, brukervennlig og skalerbar skapadministrasjon tilpasset helseinstitusjoner.

## Innhold

* [Funksjonalitet](#funksjonalitet)
* [Systemarkitektur](#systemarkitektur)
* [Installasjon](#installasjon)
* [Teknologier brukt](#teknologier-brukt)
* [Bruk](#bruk)
* [API-endepunkter](#api-endepunkter)
* [Testing](#testing)
* [Videre arbeid](#videre-arbeid)

---

## Funksjonalitet

* **RFID-autentisering** av brukere
* **Reservasjon og frigjøring** av skap
* **Automatisk utlogging** av brukere etter en gitt tidsperiode
* **Statistikk** over bruksmønster og skapaktivitet
* **Administratorverktøy** for åpning av skap, oversikt, merknader m.m.
* **Sikkerhetslag** med JWT-basert autentisering
* **Backup og restore** av database via adminpanel

## Systemarkitektur

* **Frontend**: React.js + HTML/CSS for visuell administrasjon
* **Backend**: FastAPI med Pydantic og SQLAlchemy
* **Database**: SQLite lokalt lagret på Raspberry Pi
* **Maskinvare**: Raspberry Pi + RFID-leser + relékort + magnetlås

## Installasjon

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm start
```

### Maskinvare

* Installer Raspberry Pi OS
* Koble opp RFID-leser via UART
* Koble relé og magnetlås til GPIO-pins

## Teknologier brukt

* **Python 3.13**
* **FastAPI** - API-rammeverk med Swagger UI
* **SQLite** - Lettvekts relasjonsdatabase
* **React.js** - Dynamisk frontend
* **RPi.GPIO & serial** - Styring av maskinvare
* **JWT** - Token-basert autentisering
* **Pytest** - Automatisk testing

## Bruk

* Brukere autentiserer seg med RFID-kort
* Oppdatering av skapstatus skjer automatisk via backend
* Administrator kan se statistikk, åpne skap og gjøre endringer

## API-endepunkter

Systemet tilbyr flere REST-endepunkter for interaksjon mellom frontend, maskinvare og databasen. Nedenfor følger en oversikt over hovedfunksjonene med tilhørende ruter:

### LockerRooms

* `GET /lockerrooms` — Hent alle garderober
* `POST /lockerrooms` — Opprett ny garderobe
* `DELETE /lockerrooms/{id}` — Slett en garderobe

### Lockers

* `GET /lockers` — Hent alle skap
* `POST /lockers/create_multiple` — Opprett flere skap
* `PUT /lockers/note/{locker_id}` — Oppdater merknad på skap
* `POST /lockers/reserve` — Reserver skap for bruker
* `POST /lockers/open/{locker_id}` — Åpne skap manuelt (admin)

### Users

* `POST /users/create` — Registrer ny RFID-bruker
* `GET /users` — Hent alle brukere

### Admin

* `POST /admin/login` — Autentiser administrator (JWT)
* `POST /admin/create` — Opprett ny administrator
* `GET /admin` — Hent adminbrukere
* `DELETE /admin/{id}` — Slett administrator

### Statistics

* `GET /statistics/daily` — Statistikk for daglig bruk
* `GET /statistics/active-lockers` — Aktive skap

### LockerLogs

* `GET /lockerlogs` — Hent alle loggposter

### Backup & Restore

* `POST /admin/backup` — Opprett databasebackup
* `POST /admin/restore` — Gjenopprett fra backup

## Testing

* Automatisk testing kjøres med `pytest`
* Swagger UI kan brukes for manuell API-verifisering

## Videre arbeid

* Legge til støtte for to-faktor-autentisering
* Integrere WebSockets for sanntidsstatus
* Fullføre brukerrollehierarki (vaskehjelp, avdelingsleder m.m.)
* Automatisk backup til skylagring

---

> Dette prosjektet er utviklet som bacheloroppgave ved Høgskolen i Østfold i samarbeid med Sunnaas Sykehus.
