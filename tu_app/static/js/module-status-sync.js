/**
 * Module Status Sync - Sistema centralizado para sincronizar estado de análisis de módulos
 * 
 * Este archivo consolida toda la lógica de estado de análisis en un único lugar.
 * Todas las templates deben usar estas funciones en lugar de duplicar lógica.
 * 
 * Funciones públicas:
 * - syncModuleStatus(moduleId, element, type)
 * - formatStatusMessage(data)
 * - updateStatusColor(element, data)
 * - autoRefreshModuleStatus(moduleId, element, type, interval)
 */

/**
 * Obtiene el estado real del análisis de un módulo desde el backend
 * @param {number} moduleId - ID del módulo
 * @returns {Promise<Object>} Datos de estado del módulo
 */
async function fetchModuleAnalysisStatus(moduleId) {
    try {
        const response = await fetch(`/api/module/${moduleId}/analysis-status/`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        return await response.json();
    } catch (error) {
        console.error(`[STATUS-SYNC] Error fetching status for module ${moduleId}:`, error);
        return { is_analyzed: false, document_count: 0, embeddings_count: 0, analysis_status: 'error' };
    }
}

/**
 * Formatea el mensaje de estado basado en los datos reales
 * SIMPLIFICADO: Solo usa analysis_status y is_analyzed de BD
 * @param {Object} data - Datos del estado del módulo
 * @returns {Object} {text, color, icon}
 */
function formatStatusMessage(data) {
    // Lógica basada ÚNICAMENTE en is_analyzed (si hay vectores guardados)
    
    if (data.is_analyzed) {
        // Tiene vectores/embeddings guardados
        return {
            text: '✅ Vectores guardados',
            color: '#28a745',
            icon: '✅'
        };
    }
    else {
        // Sin vectores guardados
        return {
            text: `⚫ Sin vectores`,
            color: '#999',
            icon: '⚫'
        };
    }
}

/**
 * Actualiza el color y estilo del elemento según el estado
 * @param {HTMLElement} element - Elemento a actualizar
 * @param {Object} data - Datos del estado
 */
function updateStatusColor(element, data) {
    if (data.is_analyzed && data.document_count > 0) {
        // Analizado con datos - verde
        element.style.borderLeft = '3px solid #28a745';
        element.style.background = '#f0fff4';
    } else if (data.is_analyzed && data.document_count === 0) {
        // Sin datos - gris
        element.style.borderLeft = '3px solid #6c757d';
        element.style.background = '#f8f9fa';
    } else if (data.analysis_status === 'analyzing') {
        // Analizando - amarillo
        element.style.borderLeft = '3px solid #ffc107';
        element.style.background = '#fffbf0';
    } else {
        // No analizado - neutral
        element.style.borderLeft = 'none';
        element.style.background = '';
    }
}

/**
 * Sincroniza el estado de un módulo con el servidor
 * Actualiza el elemento HTML con el estado REAL
 * 
 * @param {number} moduleId - ID del módulo
 * @param {HTMLElement} element - Elemento HTML a actualizar (puede ser botón o span de estado)
 * @param {string} type - Tipo de elemento: 'button', 'status-span', 'list-item', 'card'
 */
async function syncModuleStatus(moduleId, element, type = 'button') {
    if (!element) {
        console.warn(`[STATUS-SYNC] Element not provided for module ${moduleId}`);
        return;
    }
    
    try {
        const data = await fetchModuleAnalysisStatus(moduleId);
        const status = formatStatusMessage(data);
        
        console.log(`[STATUS-SYNC] Module ${moduleId} (${type}): ${status.text}`, {
            is_analyzed: data.is_analyzed,
            document_count: data.document_count, 
            analysis_status: data.analysis_status
        });
        
        // Actualizar según el tipo de elemento
        if (type === 'button') {
            // Es un botón - Decisión SOLO basada en is_analyzed (si hay vectores guardados)
            if (data.is_analyzed) {
                // Hay vectores guardados - opción para re-analizar
                element.textContent = '🔄 Re-analizar';
                element.style.background = '#28a745';
                element.style.color = 'white';
                element.dataset.analyzed = 'true';
            } else {
                // Sin vectores guardados - analizar
                element.textContent = '🔍 Analizar';
                element.style.background = '#6c757d';
                element.style.color = 'white';
                element.dataset.analyzed = 'false';
            }
            element.disabled = false;
            
        } else if (type === 'status-span') {
            // Es un span de estado - actualizar color y texto
            element.textContent = status.text;
            element.style.color = status.color;
            element.style.fontSize = '0.8em';
            element.style.opacity = '0.9';
            
        } else if (type === 'list-item') {
            // Es un item de lista (como en chat.html) - actualizar span dentro
            let statusSpan = element.querySelector('span:not(strong)');
            
            if (!statusSpan) {
                statusSpan = document.createElement('span');
                statusSpan.style.fontSize = '0.8em';
                statusSpan.style.opacity = '0.8';
                statusSpan.style.display = 'block';
                statusSpan.style.marginTop = '2px';
                element.appendChild(statusSpan);
            }
            
            statusSpan.textContent = status.text;
            statusSpan.style.color = status.color;
            
            // Actualizar color del elemento contenedor
            updateStatusColor(element, data);
            
        } else if (type === 'card') {
            // Es una tarjeta (como en index.html) - actualizar estilos
            updateStatusColor(element, data);
            
            let statusSpan = element.querySelector('.status-text');
            if (!statusSpan) {
                statusSpan = document.createElement('div');
                statusSpan.className = 'status-text';
                statusSpan.style.fontSize = '0.85em';
                statusSpan.style.margintop = '5px';
                element.appendChild(statusSpan);
            }
            statusSpan.textContent = status.text;
            statusSpan.style.color = status.color;
        }
        
    } catch (error) {
        console.error(`[STATUS-SYNC] Error syncing module ${moduleId}:`, error);
        // En caso de error, asegurar que el elemento es usable
        if (type === 'button') {
            element.textContent = '🔍 Analizar';
            element.style.background = '#6c757d';
            element.disabled = false;
        }
    }
}

/**
 * Auto-actualiza el estado de un módulo cada X segundos
 * Útil para ver cambios en tiempo real mientras se está analizando
 * 
 * @param {number} moduleId - ID del módulo
 * @param {HTMLElement} element - Elemento a actualizar
 * @param {string} type - Tipo de elemento
 * @param {number} interval - Intervalo en ms (default: 3000)
 * @returns {number} ID del intervalo (guardalo para cancelar después con clearInterval)
 */
function autoRefreshModuleStatus(moduleId, element, type = 'button', interval = 3000) {
    console.log(`[STATUS-SYNC] Auto-refreshing module ${moduleId} every ${interval}ms`);
    
    // Sincronizar inmediatamente
    syncModuleStatus(moduleId, element, type);
    
    // Luego cada X segundos
    return setInterval(() => {
        syncModuleStatus(moduleId, element, type);
    }, interval);
}

/**
 * Detiene el auto-refresh de un módulo
 * @param {number} intervalId - ID retornado por autoRefreshModuleStatus()
 */
function stopAutoRefresh(intervalId) {
    clearInterval(intervalId);
    console.log(`[STATUS-SYNC] Auto-refresh stopped: ${intervalId}`);
}

/**
 * Sincroniza múltiples módulos a la vez
 * @param {Array<{id, element, type}>} modules - Array de módulos a sincronizar
 */
async function syncMultipleModules(modules) {
    console.log(`[STATUS-SYNC] Syncing ${modules.length} modules...`);
    
    const promises = modules.map(m => 
        syncModuleStatus(m.id, m.element, m.type || 'button')
    );
    
    await Promise.all(promises);
    console.log('[STATUS-SYNC] All modules synced');
}

// Para debugging: exportar utilidades
window.ModuleStatusSync = {
    syncModuleStatus,
    fetchModuleAnalysisStatus,
    formatStatusMessage,
    updateStatusColor,
    autoRefreshModuleStatus,
    stopAutoRefresh,
    syncMultipleModules
};

/**
 * Auto-inicialización: Sincronizar TODOS los elementos de estado cuando carga el DOM
 * Esto asegura que el estado visual sea consistente sin necesidad de llamadas manuales
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('[STATUS-SYNC-INIT] Auto-synchronizing module states on page load');
    
    // Encontrar todos los botones de análisis
    const analyzeButtons = document.querySelectorAll('[data-module-id]');
    const modules = [];
    
    analyzeButtons.forEach(btn => {
        const moduleId = btn.getAttribute('data-module-id');
        if (moduleId && !modules.find(m => m.id == moduleId)) {
            modules.push({
                id: parseInt(moduleId),
                element: btn,
                type: 'button'
            });
        }
    });
    
    // Hacer sync en paralelo de todos los módulos
    if (modules.length > 0) {
        syncMultipleModules(modules);
        console.log(`[STATUS-SYNC-INIT] Synchronized ${modules.length} module buttons`);
    }
});

console.log('[STATUS-SYNC] Module loaded - Functions available as ModuleStatusSync.*');
