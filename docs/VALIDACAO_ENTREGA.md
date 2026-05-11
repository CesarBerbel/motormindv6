# Validação da entrega

Data da validação no ambiente de geração: 2026-05-11.

## Comandos validados no ambiente

```bash
python -m compileall -q backend
```

Resultado: aprovado. Não foram encontrados erros de sintaxe Python nos módulos do backend.

## Validações não concluídas no sandbox

Os comandos abaixo estão documentados e suportados pelo projeto, mas não foram concluídos no sandbox de geração porque a instalação de dependências via `npm ci` excedeu o tempo/foi interrompida pelo ambiente e o Docker não está disponível no sandbox.

```bash
cd frontend
npm ci
npm run build
npm run test:security

cd backend
python manage.py test

docker compose up --build
```

O projeto foi preparado para esses comandos, com `package-lock.json`, `requirements.txt`, `docker-compose.yml`, Dockerfiles, `.env.example`, `.env.docker.example`, migrations e seeds incluídos no ZIP.

## Pontos críticos conferidos por inspeção

- Banco padrão configurado como PostgreSQL em `backend/config/settings.py`, `backend/.env.example`, `.env.example`, `backend/.env.docker.example` e `.env.docker.example`.
- Docker Compose com PostgreSQL, Redis, backend, worker, beat e frontend.
- Frontend com build Vite, React 18, React Router, Axios, Bootstrap 5 e React Bootstrap.
- Backend com Django REST Framework, Simple JWT via cookies HttpOnly, CORS/CSRF, django-filter, drf-spectacular, Redis/Celery e sanitização com bleach.
- Design system administrativo persistido em `WorkshopProfile`, com migration `0029_workshopprofile_design_system.py`.
- Nova aba `Configurações administrativas > Visual e formulários`, com prévia e tokens globais.
- Componentes reutilizáveis em `frontend/src/components/AdminForm.jsx` e CSS global em `frontend/src/styles.css`.
