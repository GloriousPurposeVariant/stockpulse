FROM nginx:1.27-alpine

# The default site would otherwise take precedence over ours.
RUN rm /etc/nginx/conf.d/default.conf
COPY default.conf /etc/nginx/conf.d/default.conf
