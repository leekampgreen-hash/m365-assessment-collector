FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY public/ /usr/share/nginx/html/
COPY public-v2/ /usr/share/nginx/v2/

EXPOSE 80
