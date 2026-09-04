# 🎓 University Student Attendance System (DevOps Graduation Project)

A robust, secure, and containerized web application built with **Flask** and **SQLite**, designed to revolutionize university attendance tracking by preventing proxy attendance using **Geolocation-based validation** and role-based management. Built as part of the IEEE Al-Azhar DevOps '26 task.

---

## 💡 Project Problem & Solution
* **The Problem:** Traditional paper-based attendance methods allow students to sign on behalf of absent peers, leading to inaccurate records.
* **The Solution:** A smart digital attendance system that restricts attendance logging to students physically present within a specific geographic radius defined by the professor using **Geolocation verification**.

---

## 👥 System Roles & Features
The application features 4 distinct user roles:
1. **Admin:** Full control over the system, monitoring comprehensive reports and analytics.
2. **Professor (Doctor):** 
   * Initiates attendance sessions with custom geolocation parameters.
   * Views attendance reports and student lists.
   * **Exports Excel sheets** containing detailed attendance data and statistics.
   * Tracks teaching assistants (TAs) and student counts per section.
3. **Teaching Assistant (TA):** Manages section attendance and tracks participating students.
4. **Students:** Log in to mark their attendance securely when inside the lecture/section perimeter.

---

## 🚀 Technical Stack & Architecture
* **Backend:** Python (Flask, Flask-SQLAlchemy)
* **Database:** SQLite (Secured and persisted via Docker Volumes)
* **Containerization:** Docker & Docker Compose (Multi-stage builds for optimal image size)
* **CI/CD Pipeline:** Jenkins (Automated build, push to Docker Hub, and deployment)

---

## 🛠️ Prerequisites
* Docker & Docker Compose installed on your machine.
* Git.

---

## ⚙️ Setup & Run Instructions Locally

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/mohamedgamal2007/flask-attendance-app.git](https://github.com/mohamedgamal2007/flask-attendance-app.git)
   cd flask-attendance-app
##thank you IEEE