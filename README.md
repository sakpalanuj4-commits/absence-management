# Absence Management System

A web-based absence and attendance management system for educational
institutions. Teachers mark registers from any browser, students see their own
attendance and submit absence requests, and administrators manage users,
courses and institution-wide reporting.

Built with Django, Jinja2 templates, Tailwind CSS and MySQL.

## Setup

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt

cp .env.example .env      # then edit the database credentials
```

Create the MySQL database:

```sql
CREATE DATABASE absence_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'absence_user'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON absence_management.* TO 'absence_user'@'localhost';
```

To run without a MySQL server, set `DB_ENGINE=sqlite` in `.env`.

Then:

```bash
venv/bin/python manage.py migrate
venv/bin/python manage.py seed_demo      # optional demonstration data
venv/bin/python manage.py runserver
```

Open http://127.0.0.1:8000/.

### Demonstration accounts

`seed_demo` creates 8 courses, 60 students and one term of attendance. Every
account uses the password `demo1234`:

| Role | Username |
|---|---|
| Administrator | `admin` |
| Teacher | `teacher1` ... `teacher5` |
| Student | `student001` ... `student060` |

### Styles

The CSS is compiled from `static/src/input.css` by the Tailwind CLI:

```bash
curl -sL -o tools/tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64
chmod +x tools/tailwindcss

./tools/tailwindcss -i static/src/input.css -o static/css/app.css --minify
./tools/tailwindcss -i static/src/input.css -o static/css/app.css --watch   # during development
```

Rebuild after adding new Tailwind classes to a template.

## Using the system

**Administrator** - create departments and courses, assign teachers, enrol
students (individually or by CSV), generate the term's class sessions, review
institution-wide reports and set the attendance threshold.

**Teacher** - the dashboard lists today's classes and any register not yet
taken. Opening a register shows the enrolled students; use *Mark all present*
then change the exceptions and save. Absence requests for your courses are
approved or rejected from the *Absence requests* page.

**Student** - see your attendance percentage per course, browse your full
history, and submit an absence request with an optional supporting document.
Approved requests turn the affected sessions from absent into excused.

### Attendance percentage

`(present + late + excused) / registers taken * 100`

Cancelled sessions never count, and a session whose register has not been taken
yet does not count either - an unmarked register is not an absence. The
calculation lives in `reports/services.py` and every dashboard, report and
export uses it.

### Daily digest

Email administrators a summary of unexplained absences:

```bash
venv/bin/python manage.py send_absence_digest --days 1
```

Run it from cron, for example at 18:00 daily:

```
0 18 * * * /path/to/venv/bin/python /path/to/manage.py send_absence_digest
```

### CSV import formats

Users (`/accounts/users/import/`):

```csv
username,first_name,last_name,email,role,password
jsmith,Jo,Smith,jo.smith@example.ac.uk,STUDENT,
```

Enrolments (`/academics/enrolments/import/`):

```csv
username,course_code
jsmith,CS101
```

Rejected rows are reported line by line with the reason; valid rows are still
imported. Imported users must change their password at first login.

## Tests

```bash
venv/bin/python -m pytest          # 47 tests, runs on in-memory SQLite
venv/bin/python -m flake8 accounts academics attendance reports config tests
```

`tests/smoke_check.py` walks every page as each role against the seeded
development database and reports the status codes:

```bash
venv/bin/python tests/smoke_check.py
```

## Project layout

| Path | Contents |
|---|---|
| `config/` | Settings, URLs, Jinja2 environment, error handlers |
| `accounts/` | User model, authentication, roles, notifications, user admin |
| `academics/` | Departments, courses, enrolments, class sessions |
| `attendance/` | Attendance records, register marking, absence requests |
| `reports/` | Attendance calculations, dashboards, charts, CSV/PDF export |
| `templates/` | Jinja2 templates; shared macros in `components/macros.html` |
| `static/` | Tailwind source and build, Chart.js, register and chart scripts |
| `tests/` | pytest suite and the smoke check |

## Notes

- The PDF export uses WeasyPrint, which needs the system libraries `libpango`
  and `libcairo`. If they are missing the export serves a printable HTML page
  instead; CSV export is unaffected.
- Attachments on absence requests are limited to PDF and image files of 5 MB.
- Set `DEBUG=False` in `.env` for deployment - secure cookies, HSTS and SSL
  redirect switch on automatically.
