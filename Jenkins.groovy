//def somelibrary = evaluate readTrusted('JenkinsLibrary.groovy') 
def PARAMS_A = [
    string(name: 'VERSION'),
]
def PARAMS_B = [
    string(name: 'APP'),
]


pipeline {
    agent any
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

        stage("setup parameters"){
            steps {
                echo 'Combining common and webservice specific params'
                echo "${PARAMS_A}"
                script {
                    properties([parameters(PARAMS_A + PARAMS_B)]);
                }
            }
        }

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

def setup_parameters(){
    properties([parameters(combined_params)])
}