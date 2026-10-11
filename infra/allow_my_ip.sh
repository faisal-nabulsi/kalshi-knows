#!/usr/bin/env bash
# Campus wifi changes our public IP: re-allow SSH from the current one.
SG=$(aws ec2 describe-security-groups --region us-east-1 --filters Name=group-name,Values=degen-oracle-hackathon-sg --query 'SecurityGroups[0].GroupId' --output text)
aws ec2 authorize-security-group-ingress --region us-east-1 --group-id $SG --protocol tcp --port 22 --cidr $(curl -s https://checkip.amazonaws.com)/32 >/dev/null 2>&1; echo "allowed $(curl -s https://checkip.amazonaws.com)"
