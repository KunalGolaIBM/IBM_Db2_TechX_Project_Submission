import sys
sys.path.append(r'C:/DB2 hack/IBM_Db2_TechX_Project_Submission/IBM_Db2_TechX_Project_Submission/submissions/coldchain-guardian/backend')
from app.agents.recommendation import _generate_rules
rules = _generate_rules('HIGH','HIGH',6.5,'HIGH')
print('Number of rules:', len(rules))
for r in rules:
    print(r)
