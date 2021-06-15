
pipeline {
    agent any
    
    parameters {
        string(name: 'VERSION', defaultValue: '')
    }

    stages {

        stage ("run tests"){
          steps {
             echo 'running some tests'
            }
        }

        stage("build") {
            steps {
                echo "building docker image version $VERSION"
            }
        }

        stage("deploy"){
            steps {
                echo 'deploying docker image'
            }

        }

    }
}
