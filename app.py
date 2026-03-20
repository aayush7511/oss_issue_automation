from flask import Flask
import types
import os
import requests
import schedule
import time
import threading


app = Flask(__name__)

@app.route("/health")
def health():
    return "ok", 200

app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def formatTextForRichText(text):
    arr = []
    prev = 0
    for i in range(0, len(text), 1999):
        arr.append(
            {
                "text": {
                    "content": f"{text[i:i+2000]}",
                    }
            }
        )

    return arr

def getOpenGoodFirstIssues(repos: list):
    headers = {
        'Authorization': os.environ.get("GITHUB_TOKEN"),
        'X-GitHub-Api-Version': '2026-03-10'
        }
    issues = []
    for repo in repos:
        payload = {'state': 'open', 'labels': 'good first issue', 'sort': 'created', 'direction': 'asc'}
  
        r = requests.get(f"https://api.github.com/repos/{repo['owner']}/{repo['name']}/issues", params=payload, headers=headers)
        issues_arr = r.json()
        repo_issues = []
        for i in issues_arr:
            
            repo_issues.append(
                {
                    'node_id': i["node_id"],
                    'created_at': i["created_at"],
                    'author_association': i["author_association"],
                    'title': i["title"],
                    'labels': [x['name'] for x in i['labels']],
                    'state': i["state"],
                    'body': i["body"],   
                    'repo_url': i["repository_url"],
                    'issue_url': i["html_url"]
                }
            )
            try:
                repo_issues[-1]['assignee'] = [i["assignee"]["login"]]
            except KeyError:
                repo_issues[-1]['assignee'] = []
                
        print(f"Found {len(repo_issues)} issues in {repo['name']}")
        issues.extend(repo_issues)
    return issues
        
        
def addIssuesToNotion(issues):
    data_source_id = '3292490d-d1cd-806d-9ec7-000b97004545'
    pages_url = "https://api.notion.com/v1/pages"
    datasource_url = f"https://api.notion.com/v1/data_sources/{data_source_id}"
    page_retreival_url = f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    
    
    headers = {
        "Notion-Version": "2026-03-11",
        "Authorization": os.environ.get("NOTION_TOKEN"),
        "Content-Type": "application/json"
    }
    
    print(f"Recieved {len(issues)} issues to add to Database")
    print("Checking for Duplicates")
    newIssueFound = False
    for issue in issues:
        retrieve_db_entries = {
        "sorts": [
            {
                "property": "id",
                "direction": "ascending"
            }
        ],
        "filter": {
            "property": "id",
            "rich_text": {
                "equals": f"{issue['node_id']}"
            }
        },
        "in_trash": False,
        "result_type": "page"
        }
        

        response = requests.post(page_retreival_url, json=retrieve_db_entries, headers=headers)
        resp_arr = response.json()
        
        
        
        if(len(resp_arr['results']) == 0):
            newIssueFound = True
            chunked_text = formatTextForRichText(issue['body'])
        
            add_page = {
                "parent": {
                    "data_source_id": f"{data_source_id}",
                    "type": "data_source_id"
                },
                "properties": { 
                    "Title": {
                        "title": [
                            {
                                "text": {
                                    "content": issue['title']
                                }
                            }
                        ]
                    },
                    "id": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": f"{issue['node_id']}",
                                }
                            }
                        ]
                    },
                    "Date Opened": {
                        "rich_text": [
                            {
                                "text":{ 
                                    "content": f"{(issue['created_at']).split("T")[0]}"
                                }
                            }
                        ]
                    },
                    "Repo URL": {
                        "url": f"{issue['repo_url']}"  
                    },
                    "Issue URL": {
                        "url": f"{issue['issue_url']}"  
                    },
                    "state": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": f"{issue['state']}",
                                }
                            }
                        ]
                    },
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": chunked_text
                        }
                    }
                ]
            }
            r = requests.post(pages_url, json=add_page, headers=headers)
            json_response = r.json()
            if('object' in json_response):
                print(f"Added {json_response['properties']['Title']['title'][0]['text']['content']} to Tasks Tracker") 
             
    if(not newIssueFound):
        print("No new Issues found")
    
def searchAndInsert():
    issues = getOpenGoodFirstIssues([
        {'owner': 'vllm-project', 'name': 'vllm'},
        {'owner': 'vllm-project', 'name': 'llm-compressor'},
        {'owner': 'huggingface', 'name': 'trl'},
        {'owner': 'huggingface', 'name': 'accelerate'},
        {'owner': 'huggingface', 'name': 'transformers'},
        {'owner': 'huggingface', 'name': 'peft'},
        {'owner': 'deepspeedai', 'name': 'DeepSpeed'},
    ])
    
    addIssuesToNotion(issues)    

schedule.every().hour.do(searchAndInsert)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    thread = threading.Thread(target=run_scheduler)
    thread.daemon = True
    thread.start()
    app.run(debug=True, use_reloader=False)