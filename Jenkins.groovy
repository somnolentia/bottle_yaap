//def somelibrary = evaluate readTrusted('JenkinsLibrary.groovy') 
def params_a = [
    string(name: 'VERSION')
]
def params_b = [
    string(name: 'APP')
]

def method_setup_parameters(){
    def combined_params = params_a + params_b
    properties([parameters(combined_params)])
}
pipeline {
    agent any

    method_setup_parameters()
    //parameters {
    //    persistentString(
    //        name: 'VERSION',
    //        defaultValue: 'Some value',
    //        description: 'Provide the version number',
    //        successfulOnly: false)
    //    string(
    //        name: 'NOPERSIST',
    //        defaultValue: 'no idea',
    //        description: 'Will not persist'
    //    )
    //}

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
