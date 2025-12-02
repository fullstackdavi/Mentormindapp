document.addEventListener('DOMContentLoaded', function() {
    const hour = new Date().getHours();
    if (hour >= 22 || hour < 6) {
        document.body.classList.add('night-mode');
    }

    // Video Background - Sistema Otimizado para Performance
    const video = document.getElementById('bgVideo');
    const videoContainer = document.getElementById('video-container');
    const fallback = document.querySelector('.video-fallback');
    
    if (video) {
        // Detectar tipo de dispositivo e conexão
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth <= 768;
        const isSlowConnection = navigator.connection && (navigator.connection.saveData || navigator.connection.effectiveType === 'slow-2g' || navigator.connection.effectiveType === '2g');
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        
        // Configurar atributos essenciais
        video.muted = true;
        video.loop = true;
        video.controls = false;
        video.setAttribute('playsinline', 'true');
        video.setAttribute('webkit-playsinline', 'true');
        video.setAttribute('muted', '');
        video.setAttribute('disablepictureinpicture', '');
        video.setAttribute('disableremoteplayback', '');
        video.preload = isMobile ? 'metadata' : 'auto';
        
        // Se preferir movimento reduzido ou conexão muito lenta, usar fallback estático
        if (prefersReducedMotion || (isSlowConnection && isMobile)) {
            video.style.display = 'none';
            if (fallback) fallback.style.display = 'block';
            return;
        }
        
        // Selecionar fonte do vídeo baseado no dispositivo
        const videoSrc = isMobile ? '/static/background-mobile.mp4' : '/static/background.mp4';
        
        // Criar source element dinamicamente
        const source = document.createElement('source');
        source.src = videoSrc;
        source.type = 'video/mp4';
        video.appendChild(source);
        
        // Marcar como carregando
        video.classList.add('loading');
        
        // Função otimizada para reproduzir vídeo
        let playAttempts = 0;
        const maxAttempts = 3;
        
        function playVideo() {
            if (video.paused && playAttempts < maxAttempts) {
                playAttempts++;
                video.muted = true;
                const playPromise = video.play();
                if (playPromise !== undefined) {
                    playPromise.then(function() {
                        video.classList.remove('loading');
                        video.classList.add('playing');
                        if (fallback) fallback.style.display = 'none';
                    }).catch(function(error) {
                        if (playAttempts < maxAttempts) {
                            setTimeout(playVideo, 200);
                        }
                    });
                }
            }
        }
        
        // Eventos de carregamento otimizados
        video.addEventListener('loadedmetadata', function() {
            video.classList.remove('loading');
        }, { passive: true, once: true });
        
        video.addEventListener('canplaythrough', function() {
            playVideo();
        }, { passive: true, once: true });
        
        video.addEventListener('canplay', playVideo, { passive: true });
        
        // Loop suave
        video.addEventListener('timeupdate', function() {
            if (video.duration && video.currentTime > video.duration - 0.2) {
                video.currentTime = 0;
            }
        }, { passive: true });
        
        // Reiniciar se pausar
        video.addEventListener('pause', function() {
            if (!document.hidden) {
                requestAnimationFrame(playVideo);
            }
        }, { passive: true });
        
        // Retomar quando voltar para a aba
        document.addEventListener('visibilitychange', function() {
            if (!document.hidden && video.paused) {
                playAttempts = 0;
                playVideo();
            }
        }, { passive: true });
        
        // Para mobile: reproduzir no primeiro toque/interação
        let hasInteracted = false;
        function onFirstInteraction() {
            if (!hasInteracted) {
                hasInteracted = true;
                playAttempts = 0;
                playVideo();
                ['touchstart', 'touchend', 'click', 'scroll'].forEach(function(evt) {
                    document.removeEventListener(evt, onFirstInteraction);
                });
            }
        }
        
        ['touchstart', 'touchend', 'click', 'scroll'].forEach(function(evt) {
            document.addEventListener(evt, onFirstInteraction, { passive: true });
        });
        
        // Carregar vídeo
        video.load();
        
        // Tentar reproduzir após pequeno delay
        setTimeout(playVideo, 100);
        setTimeout(playVideo, 500);
        
        // Fallback final se vídeo não carregar em 5s
        setTimeout(function() {
            if (video.readyState < 3) {
                video.classList.remove('loading');
                if (fallback) {
                    fallback.style.opacity = '1';
                }
            }
        }, 5000);
    }

    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

function showNotification(message, type = 'success') {
    const container = document.querySelector('.container') || document.body;
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        ${message}
    `;
    container.insertBefore(alert, container.firstChild);

    setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        setTimeout(() => alert.remove(), 300);
    }, 5000);
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
}

async function apiCall(url, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
    });
}

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth'
            });
        }
    });
});

const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

document.querySelectorAll('.card, .stat-card, .feature-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
});