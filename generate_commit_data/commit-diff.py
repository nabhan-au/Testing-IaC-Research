import git
import os
import subprocess
import copy
import csv
from unidiff import PatchSet
from io import StringIO
from pathlib import Path

def get_change_list(uni_diff_text):
    patch_set = PatchSet(StringIO(uni_diff_text))

    change_list = []  # list of changes 
                  # [(file_name, [row_number_of_deleted_line],
                  # [row_number_of_added_lines]), ... ]

    for patched_file in patch_set:
        file_path = patched_file.path  # file name
        # print('file name :' + file_path)
        del_line_no = [line.target_line_no 
                   for hunk in patched_file for line in hunk 
                   if line.is_added and
                   line.value.strip() != '']  # the row number of deleted lines
        # print('deleted lines : ' + str(del_line_no))
        ad_line_no = [line.source_line_no for hunk in patched_file 
                  for line in hunk if line.is_removed and
                  line.value.strip() != '']   # the row number of added liens
        # print('added lines : ' + str(ad_line_no))
        change_list.append((file_path, del_line_no, ad_line_no))
    return change_list

def change_tuple_to_list(change_list):
    for i in range(len(change_list)):
        change_list[i] = list(change_list[i])

def run_script(run_script):
    p = subprocess.Popen(run_script)
    p.wait()

def get_file_path(change_list, repo_path):
    for change in change_list:
        file_path = os.path.join(repo_path, change[0])
        change[0] = os.path.realpath(file_path)

def read_file(change_list):
    for i, change in enumerate(change_list):
        if len(change[1]) == 0:
            change_list[i].append([])
        else:
            file_path = change[0]
            file = open(file_path)
            lines = file.readlines()
            for j in range(len(lines)):
                lines[j] = lines[j].strip()
            change_list[i].append(lines)
        
def filter_change_list(change_list):
    new_change_list = []
    for change in change_list:
        if change[0].endswith("_test.go"):
            new_change_list.append(change)
    return new_change_list

def detect_function(change):
    function_list = []
    start_line = 0
    func = None
    open_bracket = 0
    close_bracket = 0
    for i, line in enumerate(change):
        if line.startswith("func"):
            start_line = i + 1
            func = line
            open_bracket = 0
            close_bracket = 0
        if "{" in line and func != None:
            open_bracket += 1
        if "}" in line and func != None:
            close_bracket += 1
        if open_bracket == close_bracket and open_bracket != 0 and func != None:
            func_name = func.split("func ")[1]
            if func_name.startswith("("):
                func_name = func_name.split(") ")[1].split("(")[0]
            else:
                func_name = func_name.split("(")[0]
            function_list.append((func_name, (start_line, i+1)))
            func = None
    return function_list

def get_function(change_list):
    for change in change_list:
        function_list = detect_function(change[2])
        change[2] = function_list

def filter_test_func(change_list):
    for i in range(len(change_list)):
        new_func_list = []
        for j in range(len(change_list[i][2])):
            if change_list[i][2][j][0].startswith("Test"):
                new_func_list.append(change_list[i][2][j])
        change_list[i][2] = new_func_list
        
def detect_test_change(commit_sha, change_list):
    test_change_list = []
    for file in change_list:
        for func in file[2]:
            for line in file[1]:
                if line >= func[1][0] and line <= func[1][1]:
                    temp = [commit_sha, file[0], func[0]]
                    if temp not in test_change_list:
                        test_change_list.append(temp)
    return test_change_list

def run(commit_sha, repo_name, base_path, commit_change_list):
    base_clone_path = f'{base_path}/clone_repo'
    commit_repo_path = f'{base_clone_path}/{repo_name.split("/")[1]}-{commit_sha}/'
    if not os.path.isdir(commit_repo_path):
        run_script(["sh", base_path + "/script_download_repo.sh",
                repo_name, commit_sha, base_clone_path])
    get_file_path(commit_change_list, commit_repo_path)
    read_file(commit_change_list)
    get_function(commit_change_list)
    filter_test_func(commit_change_list)
    result = detect_test_change(commit_sha, commit_change_list)
    return result

def get_diff(commit_sha, parrent_commit_sha, repo_name, base_path):
    repo_path = f'{base_path}/clone_repo/{repo_name.split("/")[0]}_{repo_name.split("/")[1]}/'
    try:
        repository = git.Repo.clone_from(
        f'git@github.com:{repo_name}.git',
        repo_path
    )
    except:
        repository = git.Repo(repo_path)
    commit = repository.commit(commit_sha)
    if (len(commit.parents) == 0):
        print("This is the first commit in the repository")
    uni_diff_text = repository.git.diff(commit_sha, commit_sha+ '~1',
                                    ignore_blank_lines=True, 
                                    ignore_space_at_eol=True)

    change_list = get_change_list(uni_diff_text)
    change_list = filter_change_list(change_list)
    change_list = [change_list[0]]
    change_tuple_to_list(change_list)
    
    result = []
    #base commit
    base_commit_change_list = copy.deepcopy(change_list)
    for i in range(len(base_commit_change_list)):
        del base_commit_change_list[i][1]
    result_base_commit = run(commit_sha, repo_name, base_path, base_commit_change_list)
    
    #parent_commit
    parrent_commit_change_list = copy.deepcopy(change_list)
    for i in range(len(parrent_commit_change_list)):
        del parrent_commit_change_list[i][2]
    result_parrent_commit = run(parrent_commit_sha, repo_name, base_path, parrent_commit_change_list)
    
    result = result_base_commit + result_parrent_commit
    save_result(result, repo_name, commit_sha, base_path)
    
def save_result(change_list, repo_name, commit_sha, base_path):
    new_change_list = []
    for change in change_list:
        new_change_list.append({"repo_name": repo_name, "commit_sha": commit_sha, "file_commit_sha": change[0], "file_path": change[1], "function_name": change[2]})
    save_data_to_csv(new_change_list, os.path.join(base_path, "output", f"{repo_name.replace('/', '_')}" + "_commit_diff.csv"))

def save_data_to_csv(change_list, csv_file_name = None, columns = ["repo_name", "commit_sha", "file_commit_sha", "file_path", "function_name"]):
    file_exists = os.path.isfile(csv_file_name)
    with open(csv_file_name, "a", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for data in change_list:
            writer.writerow(data)
        f.close()
        
def read_csv_file(csv_file_name):
    with open(csv_file_name, newline='') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    return data

# repository name ex. actions/actions-runner-controller
repo = ""
#current path
base_path = ""
# processed output file from commit-info.py
input_file = ""

repo_csv = read_csv_file(input_file)
for row in repo_csv:
    get_diff(row["commit_sha"], row["parent_sha"], repo, base_path)