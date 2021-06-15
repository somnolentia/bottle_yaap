parameters {
    string(name: 'VERSION', defaultValue: '')
}

pipeline {
    agent any
    
    stages {

        stage ("run tests"){
          steps {
             echo 'running some tests'
            }
        }

        stage("build") {
            steps {
                echo 'building docker image'
            }
        }

        stage("deploy"){
            steps {
                echo 'deploying docker image'
            }

        }

    }
}
