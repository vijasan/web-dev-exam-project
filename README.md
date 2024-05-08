1. make sure your arangodb folder is empty, before pushing
2. to start write: docker-compose up
   - if you get any errors try:
   - make sure all docker containers are stopped, before starting docker container
   - make sure tailwind is running, cd into the tailwind folder and write this: npx tailwindcss -i input.css -o ../app.css --watch
