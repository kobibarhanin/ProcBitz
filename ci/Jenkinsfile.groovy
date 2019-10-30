pipeline {

    agent { label 'master'}

    stages {
        stage("Prepare") {
            steps {
                script {
                    echo "preparing"
                    boxAgent = 'agent_1';
                    googleAgent = 'master';
                }
            }      
        }
        stage("Box API tests") {
            agent { label boxAgent }
            steps {
                script {
                    echo "running"
                    for (i=0; i<5; i++){
                        Integer x = i;
                        build job: 'job_temp', parameters: [string(name: 'ID', value: x.toString())]
                    }
                }
            }
        }
    }
}
