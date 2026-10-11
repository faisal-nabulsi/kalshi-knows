#!/usr/bin/env bash
# Launch the disposable GPU training box (g6e.xlarge -> fallback g5.2xlarge). Re-runnable.
set -euo pipefail
R=us-east-1; NAME=degen-oracle-hackathon; KEY=hackathon-degen; PEM=~/.ssh/$KEY.pem
AMI=$(aws ssm get-parameter --region $R --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id --query Parameter.Value --output text)
MYIP=$(curl -s https://checkip.amazonaws.com)
if [ ! -f "$PEM" ]; then
  aws ec2 delete-key-pair --region $R --key-name $KEY >/dev/null 2>&1 || true
  aws ec2 create-key-pair --region $R --key-name $KEY --query KeyMaterial --output text > "$PEM"; chmod 600 "$PEM"
fi
SG=$(aws ec2 describe-security-groups --region $R --filters Name=group-name,Values=$NAME-sg --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)
if [ "$SG" = "None" ]; then
  SG=$(aws ec2 create-security-group --region $R --group-name $NAME-sg --description "SSH from my IP only" --query GroupId --output text)
fi
aws ec2 authorize-security-group-ingress --region $R --group-id $SG --protocol tcp --port 22 --cidr $MYIP/32 >/dev/null 2>&1 || true
for TYPE in g6e.xlarge g5.2xlarge; do
  ID=$(aws ec2 run-instances --region $R --image-id $AMI --instance-type $TYPE --key-name $KEY \
    --security-group-ids $SG --instance-initiated-shutdown-behavior terminate \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=200,VolumeType=gp3,DeleteOnTermination=true}' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
    --query 'Instances[0].InstanceId' --output text 2>/tmp/launch_err.txt) && { echo "launched $ID ($TYPE)"; break; } || { echo "$TYPE failed: $(head -c 300 /tmp/launch_err.txt)"; }
done
echo "$ID" > infra/instance_id.txt
aws ec2 wait instance-running --region $R --instance-ids $ID
IP=$(aws ec2 describe-instances --region $R --instance-ids $ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "$IP" > infra/instance_ip.txt; echo "running at $IP"
