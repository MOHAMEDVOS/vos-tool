# Railway Setup Checklist

- [ ] Backend service uses `backend/Dockerfile`
- [ ] Webapp service uses `webapp/Dockerfile`
- [ ] Backend has `FRONTEND_URL` set to the public webapp URL
- [ ] PostgreSQL variables are configured
- [ ] `SECRET_KEY` and `JWT_SECRET` are configured
- [ ] Webapp is reachable on port `3000`
- [ ] Backend `/health` is reachable
