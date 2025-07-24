# IP Monitor

Un servicio Dockerizado que monitorea cambios en la dirección IP pública usando Apify y envía notificaciones a Discord cuando detecta cambios.

## Características

- 🔍 Monitoreo continuo de la IP pública usando la API de Apify
- 📢 Notificaciones automáticas a Discord cuando cambia la IP
- 🌐 Actualización automática del registro DNS A en Hostinger
- 💾 Persistencia de datos entre reinicios
- 🐳 Completamente dockerizado
- 🔐 Ejecuta con usuario no privilegiado

## Configuración

### Variables de Entorno Requeridas

Crea un archivo `.env` en el directorio del proyecto con las siguientes variables:

```env
# URL del webhook de Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url

# Configuración de Hostinger DNS
HOSTINGER_DOMAIN=tudominio.com
HOSTINGER_RECORD_NAME=www
HOSTINGER_API_KEY=tu_api_key_de_hostinger

# Intervalo de verificación en segundos (opcional, por defecto 300 = 5 minutos)
CHECK_INTERVAL=300
```

### Configurar Hostinger DNS

1. Ve a tu panel de control de Hostinger
2. Ve a "Zona DNS" o "DNS Zone" 
3. Obtén tu API key desde la sección de desarrolladores
4. Configura las variables de entorno:
   - `HOSTINGER_DOMAIN`: Tu dominio (ej: `midominio.com`)
   - `HOSTINGER_RECORD_NAME`: El nombre del registro A (ej: `www`, `@`, `subdomain`)
   - `HOSTINGER_API_KEY`: Tu API key de Hostinger


### Configurar Webhook de Discord

1. Ve a tu servidor de Discord
2. Ve a la configuración del canal donde quieres recibir notificaciones
3. Ve a "Integraciones" > "Webhooks"
4. Crea un nuevo webhook
5. Copia la URL del webhook a tu archivo `.env`

## Uso

### Con Docker Compose (Recomendado)

```bash
# Construir e iniciar el servicio
docker compose up -d

# Ver logs
docker compose logs -f ip-monitor

# Detener el servicio
docker compose down
```

### Con Docker

```bash
# Construir la imagen
docker build -t ip-monitor .

# Ejecutar el contenedor
docker run -d \
  --name ip-monitor \
  --restart unless-stopped \
  -v ip_data:/data \
  -e APIFY_TOKEN=your_token \
  -e DISCORD_WEBHOOK_URL=your_webhook_url \
  -e CHECK_INTERVAL=300 \
  ip-monitor
```

### Desarrollo Local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
export APIFY_TOKEN=your_token
export DISCORD_WEBHOOK_URL=your_webhook_url
export CHECK_INTERVAL=300

# Ejecutar
python main.py
```

## Funcionamiento

1. **Inicio**: El servicio obtiene la IP pública actual y envía una notificación de inicio a Discord
2. **Monitoreo**: Cada 5 minutos (configurable), verifica la IP pública actual
3. **Detección de Cambios**: Si la IP ha cambiado, envía una notificación detallada a Discord
4. **Persistencia**: Guarda la IP actual en `/data/last_ip.json` para persistir entre reinicios
5. **Recuperación**: En caso de error con Apify, usa un servicio de respaldo para obtener la IP

## Logs

El servicio genera logs detallados que incluyen:
- Inicio del servicio
- IPs obtenidas
- Cambios detectados
- Notificaciones enviadas
- Errores y recuperación


## Troubleshooting

### El servicio no inicia
- Verifica que las variables de entorno estén correctamente configuradas
- Revisa los logs con `docker compose logs ip-monitor`

### No recibo notificaciones en Discord
- Verifica que la URL del webhook sea correcta
- Prueba el webhook manualmente
- Revisa los logs para errores de red

### Errores de Apify
- Verifica que el token de API sea válido

## Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request
