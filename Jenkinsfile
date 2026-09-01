pipeline {
    agent any

    environment {
        IMAGE_NAME = "ongaji-back"
        CONTAINER_NAME = "ongaji-back"
        SLACK_CHANNEL = "#4조-빌드및-pr알림"
    }

    stages {
        stage('Checkout') {
            steps {
                git branch: 'release',
                    url: 'https://github.com/sesac-final-proj/back.git',
                    credentialsId: 'mrmushdog777'
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .'
                sh 'docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest'
            }
        }

        stage('Deploy') {
            steps {
                // 실서버 .env를 Jenkins Secret file 크레덴셜(ongaji-back-env)로 등록해서 사용
                withCredentials([file(credentialsId: 'ongaji-back-env', variable: 'ENV_FILE')]) {
                    sh '''
                        docker stop ${CONTAINER_NAME} || true
                        docker rm ${CONTAINER_NAME} || true
                        docker run -d \
                            --name ${CONTAINER_NAME} \
                            -p 8000:8000 \
                            --env-file ${ENV_FILE} \
                            --restart unless-stopped \
                            ${IMAGE_NAME}:latest
                    '''
                }
            }
        }

        stage('Cleanup Old Images') {
            steps {
                sh '''
                    docker images ${IMAGE_NAME} --format "{{.Tag}}" | grep -v latest | sort -rn | tail -n +4 | xargs -r -I {} docker rmi ${IMAGE_NAME}:{} || true
                '''
            }
        }
    }

    post {
        success {
            echo 'Build & Deploy succeeded!'
            slackSend(
                channel: "${SLACK_CHANNEL}",
                color: 'good',
                message: "✅ *${env.JOB_NAME}* #${env.BUILD_NUMBER} Ongaji Backend 배포 성공\n${env.BUILD_URL}"
            )
        }
        failure {
            echo 'Build failed. Check console output.'
            slackSend(
                channel: "${SLACK_CHANNEL}",
                color: 'danger',
                message: "❌ *${env.JOB_NAME}* #${env.BUILD_NUMBER} Ongaji Backend 배포 실패\n${env.BUILD_URL}console"
            )
        }
    }
}
