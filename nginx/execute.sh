#!/bin/bash

readonly template_filepath=/etc/nginx/templates/default.template
readonly conf_filepath=/etc/nginx/conf.d/default.conf

if [ "${BACKEND_EXECUTABLE_TYPE}" = "production" ]; then
  # ==================
  # = initialization =
  # ==================
  # Setup cron script
  {
    echo '#!/bin/bash'
    echo ""
    echo 'echo "[start]" $(date "+%Y/%m/%d-%H:%M:%S")'
    echo "certbot renew --post-hook '/usr/sbin/nginx -s reload'"
    echo 'echo "[ end ]" $(date "+%Y/%m/%d-%H:%M:%S")'
  } > /data/cron_script.sh
  chmod 755 /data/cron_script.sh

  # Setup cron
  {
    echo '23 1 * * *' "/data/cron_script.sh"
  } > /var/spool/cron/crontabs/root

  # Get cert
  readonly certs_path=/etc/letsencrypt
  readonly domains="-d ${BASE_DOMAIN_NAME} -d *.${BASE_DOMAIN_NAME}"

  if [ ! -e ${certs_path}/live/${BASE_DOMAIN_NAME} ]; then
    cp -f /etc/nginx/default_certs/dhparam.pem ${certs_path}
    echo =============================================
    echo execute command
    echo certbot certonly -c /data/cli.ini ${domains}
    echo =============================================
    echo
    certbot certonly -c /data/cli.ini ${domains}
  fi
fi
# Create config file
readonly env_vars=$({
  echo '$$BACKEND_ALLOWED_HOSTS'
  echo '$$SSL_CERT_PATH'
  echo '$$SSL_CERTKEY_PATH'
  echo '$$SSL_STAPLING_VERIFY'
  echo '$$SSL_TRUSTED_CERTIFICATE_PATH'
  echo '$$VPN_ACCESS_IP'
  echo '$$VPN_ACCESS_PORT'
} | tr '\n' ' ')
cat ${template_filepath} | envsubst "${env_vars}" > ${conf_filepath}

# Define sigterm handler
is_running=1

handler(){
  echo Sigterm accepted

  is_running=0
}
trap handler 1 2 3 15

# ================
# = main routine =
# ================
echo "[nginx and cron]" $(date "+%Y/%m/%d-%H:%M:%S") start
/usr/sbin/nginx
/usr/sbin/crond

while [ ${is_running} -eq 1 ]; do
  sleep 1
done