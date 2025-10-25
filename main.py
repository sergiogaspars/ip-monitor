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
        
        # Configuración de Dokploy
        self.dokploy_enabled = os.getenv('DOKPLOY', 'false').lower() in ('true', '1', 'yes')
        self.dokploy_record_name = os.getenv('DOKPLOY_RECORD_NAME', 'dokploy')
        
        # Configuración de testing
        self.test_mode = os.getenv('TEST_MODE', 'false').lower() in ('true', '1', 'yes')
        self.test_ip = os.getenv('TEST_IP', '192.168.1.100')  # IP por defecto para testing
        
        # Discord es opcional - solo validar si se proporciona la URL
        if self.discord_webhook_url:
            logger.info("✅ Discord habilitado - se enviarán notificaciones")
        else:
            logger.warning("⚠️ Discord no configurado - no se enviarán notificaciones a Discord")
        
        if not self.hostinger_domain:
            raise ValueError("HOSTINGER_DOMAIN es requerido")

        if not self.hostinger_api_key:
            raise ValueError("HOSTINGER_API_KEY es requerido")
    
    def get_public_ip_apify(self):
        """Obtiene la IP pública usando múltiples fuentes con failover automático"""
        # Si está en modo de testing, devolver la IP de testing
        if self.test_mode:
            logger.info(f"🧪 MODO TESTING: Devolviendo IP predefinida: {self.test_ip}")
            return self.test_ip
        
        # Lista de APIs para obtener la IP pública (en orden de prioridad)
        ip_sources = [
            {
                'name': 'ipify',
                'url': 'https://api.ipify.org?format=json',
                'json_key': 'ip',
                'timeout': 10
            },
            {
                'name': 'amazonaws',
                'url': 'http://checkip.amazonaws.com/',
                'json_key': None,  # Devuelve texto plano
                'timeout': 10
            },
            {
                'name': 'whatismyip',
                'url': 'https://whatismyip.akamai.com/',
                'json_key': None,  # Devuelve texto plano
                'timeout': 10
            }
        ]
        
        last_error = None
        
        # Intentar cada fuente hasta que una funcione
        for source in ip_sources:
            try:
                logger.info(f"🔍 Intentando obtener IP desde: {source['name']}")
                response = requests.get(source['url'], timeout=source['timeout'])
                response.raise_for_status()
                
                # Parsear respuesta según el tipo
                if source['json_key']:
                    # Respuesta JSON
                    ip = response.json().get(source['json_key'])
                else:
                    # Respuesta de texto plano
                    ip = response.text.strip()
                
                # Validar que la IP sea válida
                if self._is_valid_ipv4(ip):
                    logger.info(f"✅ IP obtenida exitosamente desde {source['name']}: {ip}")
                    return ip
                else:
                    logger.warning(f"⚠️ IP inválida recibida desde {source['name']}: {ip}")
                    continue
                    
            except Exception as e:
                logger.warning(f"❌ Error obteniendo IP desde {source['name']}: {e}")
                last_error = e
                continue
        
        # Si llegamos aquí, todas las fuentes fallaron
        logger.error("🚨 TODAS las fuentes de IP fallaron")
        raise Exception(f"No se pudo obtener IP pública desde ninguna fuente. Último error: {last_error}")
    
    def _is_valid_ipv4(self, ip):
        """Valida si una cadena es una dirección IPv4 válida"""
        try:
            if not ip or not isinstance(ip, str):
                return False
            
            # Dividir por puntos
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            
            # Validar cada parte
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
                # No permitir ceros a la izquierda (excepto "0")
                if len(part) > 1 and part[0] == '0':
                    return False
            
            return True
        except (ValueError, AttributeError):
            return False
    
    def set_test_ip(self, new_test_ip):
        """Permite cambiar la IP de testing dinámicamente"""
        if self.test_mode:
            old_ip = self.test_ip
            self.test_ip = new_test_ip
            logger.info(f"🧪 TESTING: IP de testing cambiada de {old_ip} a {new_test_ip}")
        else:
            logger.warning("set_test_ip() llamado pero TEST_MODE no está habilitado")
    
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
        if not self.discord_webhook_url:
            logger.info("Discord no configurado - omitiendo notificación de cambio de IP")
            return
            
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
                        "name": "Dominio Principal",
                        "value": f"{self.hostinger_record_name}.{self.hostinger_domain}" if self.hostinger_domain else "N/A",
                        "inline": True
                    }
                ]
            }
            
            # Agregar información de Dokploy si está habilitado
            if self.dokploy_enabled:
                embed["fields"].append({
                    "name": "Dominio Dokploy",
                    "value": f"{self.dokploy_record_name}.{self.hostinger_domain}",
                    "inline": True
                })
            
            embed["fields"].append({
                "name": "Timestamp",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "inline": False
            })
            
            embed["footer"] = {
                "text": "IP Monitor"
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
        if not self.discord_webhook_url:
            logger.info("Discord no configurado - omitiendo notificación de inicio")
            return
            
        try:
            fields = [
                {
                    "name": "IP Actual",
                    "value": current_ip,
                    "inline": True
                },
                {
                    "name": "Intervalo de Verificación",
                    "value": f"{self.check_interval} segundos",
                    "inline": True
                }
            ]
            
            # Agregar información de modo testing si está habilitado
            if self.test_mode:
                fields.append({
                    "name": "🧪 Modo Testing",
                    "value": f"✅ Activo (IP: {self.test_ip})",
                    "inline": True
                })
            
            # Agregar información de Dokploy si está habilitado
            if self.dokploy_enabled:
                fields.append({
                    "name": "Dokploy",
                    "value": f"✅ Habilitado ({self.dokploy_record_name}.{self.hostinger_domain})",
                    "inline": True
                })
            
            fields.append({
                "name": "Timestamp",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "inline": False
            })
            
            # Cambiar título y color si está en modo testing
            title = "🧪 IP Monitor Iniciado (MODO TESTING)" if self.test_mode else "🚀 IP Monitor Iniciado"
            color = 0xffaa00 if self.test_mode else 0x0099ff  # Naranja para testing, azul para normal
            
            embed = {
                "title": title,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "IP Monitor" + (" - TESTING" if self.test_mode else "")
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
        if not self.discord_webhook_url:
            logger.info("Discord no configurado - omitiendo notificación de error de Hostinger")
            return
            
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
    
    def update_dokploy_dns(self, new_ip):
        """Actualiza el registro A de Dokploy en Hostinger con la nueva IP"""
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
                        "name": self.dokploy_record_name,
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
                logger.info(f"Registro DNS Dokploy actualizado exitosamente: {self.dokploy_record_name}.{self.hostinger_domain} -> {new_ip}")
                return True, None
            else:
                # Manejar diferentes tipos de errores
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_message = error_data.get('message', f'Error HTTP {response.status_code}')
                correlation_id = error_data.get('correlation_id', 'N/A')
                errors = error_data.get('errors', {})
                
                logger.error(f"Error {response.status_code} actualizando DNS Dokploy en Hostinger: {error_message}")
                if correlation_id != 'N/A':
                    logger.error(f"Correlation ID: {correlation_id}")
                
                # Enviar notificación de error a Discord con contexto de Dokploy
                self.send_dokploy_error_notification(response.status_code, error_message, correlation_id, errors, new_ip)
                
                return False, error_message
            
        except Exception as e:
            logger.error(f"Error de conexión actualizando DNS Dokploy en Hostinger: {e}")
            self.send_dokploy_error_notification(None, str(e), None, {}, new_ip)
            return False, str(e)
    
    def send_dokploy_error_notification(self, status_code, error_message, correlation_id, errors, attempted_ip):
        """Envía notificación a Discord sobre errores en la API de Hostinger para Dokploy"""
        try:
            # Determinar color y título según el tipo de error
            if status_code == 401:
                color = 0xff0000  # Rojo - Error de autenticación
                title = "🔒 Error de Autenticación en Hostinger (Dokploy)"
            elif status_code == 422:
                color = 0xff9900  # Naranja - Error de validación
                title = "⚠️ Error de Validación en Hostinger (Dokploy)"
            elif status_code == 500:
                color = 0xff0000  # Rojo - Error del servidor
                title = "💥 Error del Servidor en Hostinger (Dokploy)"
            else:
                color = 0xff0000  # Rojo - Error genérico
                title = "❌ Error en API de Hostinger (Dokploy)"
            
            fields = [
                {
                    "name": "IP Intentada",
                    "value": attempted_ip,
                    "inline": True
                },
                {
                    "name": "Registro Dokploy",
                    "value": f"{self.dokploy_record_name}.{self.hostinger_domain}",
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
                    "text": "IP Monitor - Error en Hostinger (Dokploy)"
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
            logger.info("Notificación de error de Hostinger (Dokploy) enviada a Discord")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de error de Hostinger (Dokploy) a Discord: {e}")
    
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
        last_ip, _ = self.load_last_ip()
        
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
                
                # Actualizar DNS de Dokploy si está habilitado
                if self.dokploy_enabled:
                    dokploy_success, dokploy_error_msg = self.update_dokploy_dns(current_ip)
                    if dokploy_success:
                        logger.info("DNS Dokploy actualizado exitosamente en Hostinger")
                    else:
                        logger.error(f"Error actualizando DNS Dokploy en Hostinger: {dokploy_error_msg}")
            else:
                logger.info(f"Primera ejecución, IP inicial: {current_ip}")
                # Actualizar DNS en Hostinger en la primera ejecución
                success, error_msg = self.update_hostinger_dns(current_ip)
                if success:
                    logger.info("DNS inicializado exitosamente en Hostinger")
                else:
                    logger.error(f"Error inicializando DNS en Hostinger: {error_msg}")
                
                # Actualizar DNS de Dokploy si está habilitado
                if self.dokploy_enabled:
                    dokploy_success, dokploy_error_msg = self.update_dokploy_dns(current_ip)
                    if dokploy_success:
                        logger.info("DNS Dokploy inicializado exitosamente en Hostinger")
                    else:
                        logger.error(f"Error inicializando DNS Dokploy en Hostinger: {dokploy_error_msg}")
            
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
                    
                    # Actualizar DNS de Dokploy si está habilitado
                    if self.dokploy_enabled:
                        dokploy_success, dokploy_error_msg = self.update_dokploy_dns(new_ip)
                        if dokploy_success:
                            logger.info("DNS Dokploy actualizado exitosamente en Hostinger")
                        else:
                            logger.error(f"Error actualizando DNS Dokploy en Hostinger: {dokploy_error_msg}")
                    
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
