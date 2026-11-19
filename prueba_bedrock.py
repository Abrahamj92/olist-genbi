import boto3
pruebas = [
 ("us-east-1","us.amazon.nova-lite-v1:0"),
 ("us-east-1","amazon.nova-micro-v1:0"),
 ("us-east-1","anthropic.claude-3-haiku-20240307-v1:0"),
 ("us-east-1","us.meta.llama3-2-3b-instruct-v1:0"),
 ("us-west-2","us.amazon.nova-micro-v1:0"),
 ("us-west-2","us.amazon.nova-lite-v1:0"),
 ("us-east-2","us.amazon.nova-micro-v1:0"),
]
for reg, mid in pruebas:
    try:
        c = boto3.client("bedrock-runtime", region_name=reg, config=boto3.session.Config(retries={"max_attempts":1}))
        r = c.converse(modelId=mid, messages=[{"role":"user","content":[{"text":"hola"}]}])
        print("OK   ", reg, mid, "->", r["output"]["message"]["content"][0]["text"][:40])
    except Exception as e:
        print("FALLA", reg, mid, "->", type(e).__name__, str(e)[:80])
