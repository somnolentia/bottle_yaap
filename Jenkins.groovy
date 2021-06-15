
pipeline {
    agent any

    parameters {
        persistentString(
            name: 'VERSION',
            defaultValue: 'Some value',
            description: 'Provide the version number',
            successfulOnly: false)
    }

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
