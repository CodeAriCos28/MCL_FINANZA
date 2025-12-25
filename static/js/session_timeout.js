let timeout;

function resetTimer() {
    clearTimeout(timeout);
    
    // 600000 milisegundos = 10 minutos
    timeout = setTimeout(() => {
        // Alerta estética con SweetAlert2
        Swal.fire({
            title: '¡Sesión Expirada!',
            text: 'Has estado inactivo por demasiado tiempo.',
            icon: 'warning',
            confirmButtonColor: '#035087', // El azul de tu sidebar
            confirmButtonText: 'Aceptar',
            allowOutsideClick: false // Obliga al usuario a interactuar
        }).then((result) => {
            if (result.isConfirmed) {
                window.location.href = "/logout/"; 
            }
        });

        // Redirección automática de respaldo después de 5 segundos si no hacen clic
        setTimeout(() => {
            window.location.href = "/logout/";
        }, 5000);

    }, 600000); 
}

// Eventos que se consideran "actividad"
window.onload = resetTimer;
window.onmousemove = resetTimer;
window.onmousedown = resetTimer; 
window.onkeypress = resetTimer;
window.ontouchstart = resetTimer;