pipeline {
    agent any
    
    stages {
        stage('1. Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage('2. Build Docker Image') {
            steps {
                script {
                    app = docker.build("mohamedgamal2007/flask-attendance-app:${env.BUILD_NUMBER}")
                }
            }
        }

        stage('3. Push to Docker Hub') {
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', 'dockerhub-credentials') {
                        app.push("latest")
                    }
                }
            }
        }

        stage('4. Deploy Application') {
            steps {
                sh '''
                    docker stop flask_attendance_app || true
                    docker rm flask_attendance_app || true
                    docker run -d --name flask_attendance_app -p 5000:5000 mohamedgamal2007/flask-attendance-app:latest
                '''
            }
        }
    }
}