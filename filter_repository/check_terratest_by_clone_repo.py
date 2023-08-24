from glob import glob
from dotenv import load_dotenv
import csv
import os
import shutil
import git
import time

class MyRepo:
    
    def __init__(self, repo_url, save_clone_repo_path) -> None:
        self.__repo_url = repo_url
        self.__repo_name = ""
        self.__have_terra_test = None
        self.__save_clone_repo_path = save_clone_repo_path
        
    def clone_repository(self):
        repo_name = self.__repo_url.split('/')[-1].split('.')[0]

        try:
            git.Repo(self.__save_clone_repo_path + repo_name)
        except:
            git.Repo.clone_from(self.__repo_url, self.__save_clone_repo_path + repo_name, depth=1)
        self.__repo_name = repo_name
        
    def delete_repository(self):
        if os.path.exists(self.__save_clone_repo_path + self.__repo_name) and self.__repo_name != "":
            shutil.rmtree(self.__save_clone_repo_path + self.__repo_name, ignore_errors=True)
        
    def get_repo_path(self):
        return self.__save_clone_repo_path + self.__repo_name
    
    def get_repo_url(self):
        return self.__repo_url
    
    def check_contains_terratest(self):
        print(self.get_repo_path())
        result = False
        glob_result = glob(self.get_repo_path() + "/**/go.mod", recursive=True)
        if len(glob_result) < 0:
            return False
        for file_path in glob_result:
            print(file_path)
            with open(file_path, "r") as f:
                if "github.com/gruntwork-io/terratest" in f.read():
                    result = True
        return result
    
    def get_dict(self):
        if self.__have_terra_test is None:
            self.__have_terra_test = self.check_contains_terratest()
        return {
            "repo_name": self.__repo_name,
            "repo_path": self.__repo_url,
            "contain_terra_test": self.__have_terra_test,
            "error": False
        }
        
    def get_repo_name(self):
        return self.__repo_name


# read csv file
def read_csv_file(csv_file_name):
    with open(csv_file_name, newline='') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    return data

# save data to csv file
def save_data_to_csv(repo_data_lst, csv_file_name = None, columns = ["repo_name", "repo_path", "contain_terra_test", "error"]):
    file_exists = os.path.isfile(csv_file_name)
    with open(csv_file_name, "a", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for data in repo_data_lst:
            writer.writerow(data)
        f.close()
        
def get_repo_information(repo_url, save_clone_repo_path, delete_repo = True):
    my_repo = MyRepo(repo_url, save_clone_repo_path)
    try:
        my_repo.clone_repository()
        repo_dict = my_repo.get_dict()
        if delete_repo:
            my_repo.delete_repository()
        return repo_dict
    except Exception as e:
        print(e)
        my_repo.delete_repository()
        return {
            "repo_name": my_repo.get_repo_name(),
            "repo_path": my_repo.get_repo_url(),
            "contain_terra_test": False,
            "error": True
        }
        
def check_csv_file_name(csv_file_name):
    file_exists = os.path.isfile(csv_file_name)
    num = 0
    temp_csv_file_name = None
    while file_exists:
        temp_csv_file_name = csv_file_name.split(".")[0] + "_" + str(num) + ".csv"
        file_exists = os.path.isfile(temp_csv_file_name)
        num += 1
    return csv_file_name if temp_csv_file_name is None else temp_csv_file_name

load_dotenv()
repo_url_file_name = os.getenv("REPO_URL_CSV_FILE_NAME")
save_clone_repo_path = os.getenv("SAVE_CLONE_REPO_PATH")
save_repo_information_csv_file_name = os.getenv("SAVE_REPO_INFORMATION_CSV_FILE_NAME")
sleep_time = os.getenv("SLEEP_TIME")
delete_repo = os.getenv("DELETE_REPO")
input_range = os.getenv("INPUT_RANGE")

assert repo_url_file_name is not None and repo_url_file_name != ""
assert save_clone_repo_path is not None
assert save_repo_information_csv_file_name is not None and save_repo_information_csv_file_name != ""
assert input_range is not None and input_range != ""

try:
    sleep_time = int(sleep_time)
except:
    assert False, "SLEEP_TIME must be integer"

if delete_repo in ["1", "True", "true", "TRUE"]:
    delete_repo = True
elif delete_repo in ["0", "False", "false", "FALSE"]:
    delete_repo = False
else:
    assert False, "DELETE_REPO must be boolean"
    
try:
    input_range = input_range.split("-")
    input_range = [int(input_range[0]), int(input_range[1])]
except:
    assert False, "INPUT_RANGE must be integer"

repo_urls = read_csv_file(repo_url_file_name)
repo_urls = [{"repo_url":repo_url["repo_path"]} for repo_url in repo_urls]
repo_size = len(repo_urls)
print(repo_urls)
save_repo_information_csv_file_name = check_csv_file_name(save_repo_information_csv_file_name)
for i in range(input_range[0] - 1, min(input_range[1], repo_size)):
    repo_url = repo_urls[i]
    print(repo_url)
    repo_dict = get_repo_information(repo_url["repo_url"], save_clone_repo_path, delete_repo = delete_repo)
    save_data_to_csv([repo_dict], save_repo_information_csv_file_name)
    time.sleep(sleep_time)
