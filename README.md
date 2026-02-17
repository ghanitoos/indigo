# Indigo Admin Panel

A modular web-based administration panel for school network management.

## Overview

Indigo is a comprehensive admin panel built with Flask and Docker that integrates with:
- Samba AD DC (LDAP authentication and user management)
- pfSense (firewall management)
- Samba File Server (file permissions and access control)
- BorgBackup (backup monitoring)
- FOG Project (imaging and deployment)

## Features

- **LDAP Authentication**: Seamless integration with Samba AD DC
- **Role-Based Access Control**: Granular permissions for different user groups
- **Modular Architecture**: Easy to extend with new modules
- **Docker-Based**: Isolated, reproducible deployments
- **Multilingual**: German UI with English fallback

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Access to Samba AD DC server
- Network connectivity to target systems

### Installation

1. Clone the repository:
```bash
git clone https://github.com/ghanitoos/indigo.git
cd indigo
```

2. Copy environment template and configure:
```bash
cp .env.example .env
nano .env  # Edit with your settings
```

3. Start the services:
```bash
docker compose up -d
```

4. Access the panel:
```
http://your-server-ip:8080
```

## Project Structure

```
/opt/admin-panel/
├── core-app/           # Main Flask application
├── nginx-proxy/        # Reverse proxy
├── data/               # Persistent data
└── docker-compose.yml  # Container orchestration
```

Note: The canonical location for modules is `core-app/modules/`. A legacy top-level `modules/` folder (previously containing integrations) has been removed to avoid duplication.

## Documentation

- [Architecture](ARCHITECTURE.md) - System architecture and design
- [Development](DEVELOPMENT.md) - Development setup and guidelines

## Repository

This project's Git repository is hosted on GitHub:

- Repository: https://github.com/ghanitoos/indigo.git

Updates and issue tracking are managed via the GitHub repository.

## Technology Stack

- **Backend**: Python 3.12, Flask
- **Database**: PostgreSQL 16
- **Frontend**: Jinja2 templates, vanilla JavaScript
- **Auth**: LDAP via ldap3
- **Deployment**: Docker, Docker Compose

## Contributing

This project follows strict coding standards. Please read [DEVELOPMENT.md](DEVELOPMENT.md) before contributing.

## License

Internal use only - School network administration

## Support

For issues and questions, contact the network administration team.
