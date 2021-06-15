
pipeline {
    agent any
    options([
        parameters {
            string(name: 'VERSION', defaultValue: ${params.Version}, length: 10)
        }
    ]) 

    stages {

        stage ("run tests"){
          steps {
             echo 'running some tests'
            }
        }

        stage("build") {
            steps {
                echo "building docker image version ${params.VERSION}"
            }
        }

        stage("deploy"){
            steps {
                echo 'deploying docker image'
            }

        }

    }
}
