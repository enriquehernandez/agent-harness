#!/bin/bash
# Redirigimos stderr a /dev/null para silenciar el banner del servidor
exec npx -y @modelcontextprotocol/server-filesystem@2.4.1 "$@" 2>/dev/null