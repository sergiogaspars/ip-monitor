#!/usr/bin/env python3
"""
IP Monitor - Monitorea cambios en la dirección IP pública usando Apify
y envía notificaciones a Discord cuando detecta cambios.
"""

import os
import json
import time
import logging
import requests
from datetime import datetime
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IPMonitor:
    def __init__(self):
        self.discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '300'))  # 5 minutos por defecto
        self.ip_file = Path('/data/last_ip.json')
        
        # Configuración de Hostinger
        self.hostinger_api_key = os.getenv('HOSTINGER_API_KEY')
        self.hostinger_domain = os.getenv('HOSTINGER_DOMAIN')
        self.hostinger_record_name = os.getenv('HOSTINGER_RECORD_NAME', '@')
        
        if not self.discord_webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL es requerido")
        
        if not self.hostinger_domain:
            raise ValueError("HOSTINGER_DOMAIN es requerido")

        if not self.hostinger_api_key:
            raise ValueError("HOSTINGER_API_KEY es requerido")
    
    def get_public_ip_apify(self):
        """Obtiene la IP pública"""
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=10)
            response.raise_for_status()
            ip = response.json().get('ip')
            logger.info(f"IP obtenida: {ip}")
            return ip
        except Exception as e:
            logger.error(f"Error obteniendo IP: {e}")
            raise
    
    def load_last_ip(self):
        """Carga la última IP conocida desde archivo"""
        try:
            if self.ip_file.exists():
                with open(self.ip_file, 'r') as f:
                    data = json.load(f)
                    return data.get('ip'), data.get('timestamp')
        except Exception as e:
            logger.error(f"Error cargando última IP: {e}")
        return None, None
    
    def save_current_ip(self, ip):
        """Guarda la IP actual en archivo"""
        try:
            # Crear directorio si no existe
            self.ip_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'ip': ip,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.ip_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"IP guardada: {ip}")
        except Exception as e:
            logger.error(f"Error guardando IP: {e}")
    
    def send_discord_notification(self, old_ip, new_ip):
        """Envía notificación a Discord sobre el cambio de IP"""
        try:
            embed = {
                "title": "🔄 Cambio de IP Detectado",
                "color": 0x00ff00,  # Verde
                "fields": [
                    {
                        "name": "IP Anterior",
                        "value": old_ip or "N/A",
                        "inline": True
                    },
                    {
                        "name": "Nueva IP",
                        "value": new_ip,
                        "inline": True
                    },
                    {
                        "name": "Dominio",
                        "value": f"{self.hostinger_record_name}.{self.hostinger_domain}" if self.hostinger_domain else "N/A",
                        "inline": True
                    },
                    {
                        "name": "Timestamp",
                        "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "IP Monitor"
                }
            }
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(
                self.discord_webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Notificación enviada a Discord exitosamente")
            
        except Exception as e:
            logger.error(f"Error enviando notificación a Discord: {e}")
    
    def send_startup_notification(self, current_ip):
        """Envía notificación de inicio del monitor"""
        try:
            embed = {
                "title": "🚀 IP Monitor Iniciado",
                "color": 0x0099ff,  # Azul
                "fields": [
                    {
                        "name": "IP Actual",
                        "value": current_ip,
                        "inline": True
                    },
                    {
                        "name": "Intervalo de Verificación",
                        "value": f"{self.check_interval} segundos",
                        "inline": True
                    },
                    {
                        "name": "Timestamp",
                        "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "IP Monitor"
                }
            }
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(
                self.discord_webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Notificación de inicio enviada a Discord")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de inicio: {e}")
    
    def send_hostinger_error_notification(self, status_code, error_message, correlation_id, errors, attempted_ip):
        """Envía notificación a Discord sobre errores en la API de Hostinger"""
        try:
            # Determinar color y título según el tipo de error
            if status_code == 401:
                color = 0xff0000  # Rojo - Error de autenticación
                title = "🔒 Error de Autenticación en Hostinger"
            elif status_code == 422:
                color = 0xff9900  # Naranja - Error de validación
                title = "⚠️ Error de Validación en Hostinger"
            elif status_code == 500:
                color = 0xff0000  # Rojo - Error del servidor
                title = "💥 Error del Servidor en Hostinger"
            else:
                color = 0xff0000  # Rojo - Error genérico
                title = "❌ Error en API de Hostinger"
            
            fields = [
                {
                    "name": "IP Intentada",
                    "value": attempted_ip,
                    "inline": True
                },
                {
                    "name": "Dominio",
                    "value": f"{self.hostinger_record_name}.{self.hostinger_domain}",
                    "inline": True
                },
                {
                    "name": "Código de Estado",
                    "value": str(status_code) if status_code else "Conexión Failed",
                    "inline": True
                },
                {
                    "name": "Mensaje de Error",
                    "value": error_message,
                    "inline": False
                }
            ]
            
            # Agregar correlation ID si existe
            if correlation_id:
                fields.append({
                    "name": "Correlation ID",
                    "value": correlation_id,
                    "inline": True
                })
            
            # Agregar detalles de errores de validación si existen
            if errors:
                error_details = []
                for field, field_errors in errors.items():
                    error_details.append(f"**{field}:**")
                    for error in field_errors:
                        error_details.append(f"  • {error}")
                
                if error_details:
                    fields.append({
                        "name": "Detalles del Error",
                        "value": "\n".join(error_details)[:1024],  # Limitar a 1024 caracteres
                        "inline": False
                    })
            
            fields.append({
                "name": "Timestamp",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "inline": False
            })
            
            embed = {
                "title": title,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "IP Monitor - Error en Hostinger"
                }
            }
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(
                self.discord_webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Notificación de error de Hostinger enviada a Discord")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de error de Hostinger a Discord: {e}")
    
    def update_hostinger_dns(self, new_ip):
        """Actualiza el registro A en Hostinger con la nueva IP"""
        try:
            url = f"https://developers.hostinger.com/api/dns/v1/zones/{self.hostinger_domain}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.hostinger_api_key}"
            }
            
            payload = {
                "overwrite": True,
                "zone": [
                    {
                        "name": self.hostinger_record_name,
                        "records": [
                            {
                                "content": new_ip
                            }
                        ],
                        "ttl": 300,
                        "type": "A"
                    }
                ]
            }
            
            response = requests.put(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Registro DNS actualizado exitosamente: {self.hostinger_record_name}.{self.hostinger_domain} -> {new_ip}")
                return True, None
            else:
                # Manejar diferentes tipos de errores
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_message = error_data.get('message', f'Error HTTP {response.status_code}')
                correlation_id = error_data.get('correlation_id', 'N/A')
                errors = error_data.get('errors', {})
                
                logger.error(f"Error {response.status_code} actualizando DNS en Hostinger: {error_message}")
                if correlation_id != 'N/A':
                    logger.error(f"Correlation ID: {correlation_id}")
                
                # Enviar notificación de error a Discord
                self.send_hostinger_error_notification(response.status_code, error_message, correlation_id, errors, new_ip)
                
                return False, error_message
            
        except Exception as e:
            logger.error(f"Error de conexión actualizando DNS en Hostinger: {e}")
            self.send_hostinger_error_notification(None, str(e), None, {}, new_ip)
            return False, str(e)
    
    def run(self):
        """Ejecuta el monitor principal"""
        logger.info("Iniciando IP Monitor...")
        
        # Obtener IP actual
        try:
            current_ip = self.get_public_ip_apify()
        except Exception as e:
            logger.error(f"Error obteniendo IP inicial: {e}")
            return
        
        # Cargar última IP conocida
        last_ip, last_timestamp = self.load_last_ip()
        
        # Enviar notificación de inicio
        self.send_startup_notification(current_ip)
        
        # Si es la primera ejecución o la IP cambió
        if last_ip != current_ip:
            if last_ip is not None:
                logger.info(f"Cambio de IP detectado: {last_ip} -> {current_ip}")
                self.send_discord_notification(last_ip, current_ip)
                # Actualizar DNS en Hostinger
                success, error_msg = self.update_hostinger_dns(current_ip)
                if success:
                    logger.info("DNS actualizado exitosamente en Hostinger")
                else:
                    logger.error(f"Error actualizando DNS en Hostinger: {error_msg}")
            else:
                logger.info(f"Primera ejecución, IP inicial: {current_ip}")
                # Actualizar DNS en Hostinger en la primera ejecución
                success, error_msg = self.update_hostinger_dns(current_ip)
                if success:
                    logger.info("DNS inicializado exitosamente en Hostinger")
                else:
                    logger.error(f"Error inicializando DNS en Hostinger: {error_msg}")
            
            self.save_current_ip(current_ip)
        else:
            logger.info(f"IP sin cambios: {current_ip}")
        
        # Loop de monitoreo
        while True:
            try:
                time.sleep(self.check_interval)
                
                new_ip = self.get_public_ip_apify()
                
                if new_ip != current_ip:
                    logger.info(f"Cambio de IP detectado: {current_ip} -> {new_ip}")
                    self.send_discord_notification(current_ip, new_ip)
                    # Actualizar DNS en Hostinger
                    success, error_msg = self.update_hostinger_dns(new_ip)
                    if success:
                        logger.info("DNS actualizado exitosamente en Hostinger")
                    else:
                        logger.error(f"Error actualizando DNS en Hostinger: {error_msg}")
                    
                    self.save_current_ip(new_ip)
                    current_ip = new_ip
                else:
                    logger.info(f"IP sin cambios: {current_ip}")
                    
            except KeyboardInterrupt:
                logger.info("Monitor detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"Error en el loop de monitoreo: {e}")
                time.sleep(60)  # Esperar 1 minuto antes de reintentar

if __name__ == "__main__":
    try:
        monitor = IPMonitor()
        monitor.run()
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        exit(1)
