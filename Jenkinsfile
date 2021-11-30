pipeline {
    agent any

    environment {
        ON_SUCCESS_SEND_EMAIL = true
        ON_FAILURE_SEND_EMAIL = true
    }

    parameters {
        booleanParam(name:'CLEAN_WORKSPACE',
            defaultValue:false,
            description:'Want to delete build directory?'
        )
        booleanParam(name:'TESTING_FRONTEND',
            defaultValue:false,
            description:'Want to run tests on Frontend?'
        )
    }

    tools {
        maven "MVN3"
        jdk "JDK17"
    }

    stages {
        stage('Build') {
            steps {
                echo 'Building application!'
                
                git branch: 'master', url: 'https://github.com/espada1317/spring-boot-blog-app.git'
                
                bat "mvn install -Dmaven.test.skip=true"
            }
            
            post {
                failure {
                    expression {
                        env.ON_SUCCESS_SEND_EMAIL == false
                        env.ON_FAILURE_SEND_EMAIL == true
                    }
                }
            }
        }
        
        stage('Testing Backend')
        {
            steps {
                echo 'Testing Backend stated!'
            
                bat "mvn -Dmaven.test.failure.ignore=true clean package"
            }
            
            post {
                success {
                    junit allowEmptyResults: true, testResults: '**/test-results/*.xml'
                    //junit '**/target/surefire-reports/TEST-*.xml'
                    //archiveArtifacts 'target/*.jar'
                }
                
                failure {
                    expression {
                        env.ON_SUCCESS_SEND_EMAIL == false
                        env.ON_FAILURE_SEND_EMAIL == true
                    }
                }
            }
        }
        
        stage('Testing Frontend')
        {
            when {
                expression {
                    params.TESTING_FRONTEND == true
                }
            }
            steps {
                echo "Testing Frontend! \nValue of TESTING_FRONTEND is ${env.TESTING_FRONTEND}"
            }
        }
    }
    
    post {
        always {
            script {
                if(params.CLEAN_WORKSPACE == true) {
                    echo 'Deleting directory!'
                    cleanWs()
                }
            }   
        }
        
        success {
            script {
                if(env.ON_SUCCESS_SEND_EMAIL)
                {
                    echo "Send email success job name: ${JOB_NAME}, build number: ${BUILD_NUMBER}, build url: ${BUILD_URL} "
                    emailext ( body: "Success! Job name: ${JOB_NAME}, build number: ${BUILD_NUMBER}, build url: ${BUILD_URL}", subject: 'Build Success', to: 'trifan.denis1999@gmail.com')
                    echo 'Email sent'
                }
            }
        }
        
        unstable {
            script {
                    echo "Send email unstable job name: ${JOB_NAME}, build number: ${BUILD_NUMBER}, build url: ${BUILD_URL} "
                    emailext ( body: "Unstable! Job name: ${JOB_NAME}, build number: ${BUILD_NUMBER}, build url: ${BUILD_URL}", subject: 'Build Unstable', to: 'trifan.denis1999@gmail.com')
                    echo 'Email sent'
            }
        }
        
        failure {
            script {
                if(env.ON_FAILURE_SEND_EMAIL)
                {
                    echo "Send email fail job name: ${JOB_NAME}, build number: ${BUILD_NUMBER}, build url: ${BUILD_URL} "
                    emailext ( body: "Fail! Job name: ${JOB_NAME}, build number: ${BUILD_NUMBER}, build url: ${BUILD_URL}", subject: 'Build Failure', to: 'trifan.denis1999@gmail.com')
                    echo 'Email sent'
                }
            }
        }
    }
}
