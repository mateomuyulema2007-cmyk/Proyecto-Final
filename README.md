# LogicWeb UTA 🧠

Plataforma web educativa para el aprendizaje de lógica y algoritmos de programación, desarrollada como proyecto final. Permite a estudiantes repasar teoría, resolver ejercicios interactivos y llevar un historial de su progreso.

---

## ✨ Funcionalidades

- **Autenticación** — Registro e inicio de sesión para estudiantes. Cuenta docente incluida por defecto (`profe_ruben`).
- **Módulos de teoría** — Contenido organizado por temas:
  - Variables y tipos de datos
  - Condicionales
  - Bucles y ciclos
  - Contadores y acumuladores
  - Funciones
  - POO básica
  - Comparación de lenguajes
  - Lógica, algoritmos, pseudocódigo y estructuras de control
- **Ejercicios interactivos** — El estudiante ingresa respuestas que son evaluadas automáticamente.
- **Laboratorio lógico** — Práctica libre con retroalimentación inmediata.
- **Historial y progreso** — Registro de prácticas por usuario con resumen de correctas vs. en refuerzo.
- **Retroalimentación automática** — Cada ejercicio entrega un mensaje personalizado según el resultado.

---

## 🛠️ Tecnologías

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3 + Flask |
| Base de datos | SQLite3 |
| Frontend | HTML, CSS, JavaScript (sin frameworks externos) |
| Servidor | [PythonAnywhere](LogicWeb.pythonanywhere.com) |

---

## 📁 Estructura del proyecto

```
LogicWeb_UTA/
├── app.py                  # Lógica del servidor Flask
├── base_datos.db           # Base de datos SQLite (se genera automáticamente)
└── templates/
    ├── index.html          # Dashboard principal (todos los módulos)
    ├── login.html          # Página de inicio de sesión
    └── registro.html       # Página de registro
```

---


## 🔐 Credenciales por defecto

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| `profe_ruben` | `1234` | Docente |

Los estudiantes pueden registrarse desde la pantalla de inicio.

---

## 📌 Notas

- Las contraseñas se almacenan en texto plano (proyecto académico). Para producción real se recomienda usar `werkzeug.security` o similar.
- La base de datos `base_datos.db` se crea automáticamente si no existe al iniciar la aplicación.
