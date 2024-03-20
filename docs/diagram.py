from diagrams import Diagram, Cluster
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import SNS
from diagrams.aws.network import APIGateway
from diagrams.saas.chat import Slack
from diagrams.custom import Custom

with Diagram("diagram", show=False) as diag:
    slack_app = Slack("slack app")
    openai_assistants_api = Custom("OpenAI Assistants API", "GPT.png")
    with Cluster("AWS Cloud"):
        api_gateway = APIGateway("api-gateway")
        lambda1 = Lambda("lambda")
        sns = SNS("sns")
        lambda2 = Lambda("lambda")
        slack_app >> api_gateway >> lambda1 >> sns >> lambda2 >> openai_assistants_api
