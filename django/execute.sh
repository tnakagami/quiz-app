#!/bin/bash

is_running=1

# Setup handler
handler(){
  echo sigterm accepted

  is_running=0
}
trap handler 1 2 3 15

# Copy javascript files to nginx static directory
readonly from_base_path="/var/static"
readonly to_base_path="/opt/nginx-static"

python manage.py collectstatic --noinput --clear
for target in js css img; do
  from_path=${from_base_path}/${target}
  to_path=${to_base_path}/${target}

  if [ ! -e ${to_path} ]; then
    mkdir -p ${to_path}
  fi
  cp -rf ${from_path}/* ${to_path}
done

# In the case of development environment
if [ "${DJANGO_EXECUTABLE_TYPE}" = "development" ]; then
  python manage.py runserver 0.0.0.0:8001 &
  pid=$!
# In the case of production environment
else
  daphne -b 0.0.0.0 -p 8001 --ping-interval 10 --ping-timeout 120 --proxy-headers config.asgi:application &
  pid=$!
fi

while [ ${is_running} -eq 1 ]; do
  sleep 1
done

# Finalize
kill ${pid}