from json.decoder import JSONDecodeError
import yaml
import json
import http.client
from glob import glob
from simple_term_menu import TerminalMenu
import os
import datetime

arch = "amd64"
splitchars = [".","-","_"]
composepath = '*.yml'

def parse_compose_file(filename:str):
	versions = {}
	with open(filename, 'r') as f:
		doc = yaml.load(f, Loader=yaml.FullLoader)
	if 'services' not in doc.keys():
		return versions
	for service in doc['services']:
		try:
			image, version = doc['services'][service]["image"].split(":")
		except ValueError:
			image = doc['services'][service]["image"]
			version = "latest"
		except KeyError:
			continue			
		if not "/" in image:
			image = "library/"+image
		#print(service+" : "+image+" : "+version)
		if image.count("/") == 2:
			huburl = image.split("/")
			image = huburl[1]+"/"+huburl[2]
			huburl = huburl[0]
		else:
			huburl = "hub.docker.com"
		con = http.client.HTTPSConnection(huburl,port=443)
		con.request("GET", f"/v2/repositories/{image}/tags/?page_size=100&page=1&ordering=last_updated")
		response = con.getresponse().read()
		#print(response)
		try:
			data = json.loads(response)
		except JSONDecodeError as e:
			print(e,response,image)
			continue
		tmp = []

		for tag in data["results"]:
			#find digest for arch
			try:
				match = next(d for d in tag["images"] if d['architecture'] == arch)
			#print(f'{tag["name"] : <20}{match["digest"][-8:] : >10}')
			except StopIteration:
				continue
			try:
				tmp.append({tag["name"] : match["digest"]})
			except KeyError as er:
				continue
		versions[image] = {}
		versions[image]["current"] = version
		versions[image]["available"] = tmp
		#print()
		#break
	#print(json.dumps(versions))
	return versions

def split_tag(tag:str) -> list:
	for splitchar in splitchars:
		tag = tag.replace(splitchar, " ")
	sp = tag.split(" ")
	sp = list(filter(None, sp))
	index_offset = 0
	# split alphabet and numbers in same string
	try:
		for x in range(2):
			for n, s in enumerate(sp):
				if s.isalpha() or s.isnumeric():
					continue
				if s[0].isalpha(): # string starts alphabetic
					for i in range(1,len(s)):
						if s[:-i].isalpha():
							del sp[n]
							sp[n:n] = [s[:-i], s[-i:]]
							index_offset += 1
							break 
				if s[0].isnumeric(): # string starts numeric
					for i in range(1,len(s)):
						if s[:-i].isnumeric():
							sp[n] = s[:-i]+" "+s[-i:]
							break 
	except IndexError as er:
		print(er,sp)
	return sp

# returns newer version
# 0 -> t0 newer then t1
# 1 -> t1 newer then t0
# 2 they are the same 
# 3 no valid comparison
def compare_tags(t0:list, t1:list) -> int:
	#print(t0,t1)
	if t0 == t1:
		#print("same")
		return 2
	if t0[0].isnumeric() and t1[0].isalpha():
		#print("t0 is numeric and t1 alphabetic, no way to compare")
		return 3
	if t1[0].isnumeric() and t0[0].isalpha():
		#print("t1 is numeric and t0 alphabetic, no way to compare")
		return 3		

	# different release "branch" (like different container os)
	for i in [0,-1]:
		if t0[i].isalpha() and t1[i].isalpha() and t0[i] != t1[i]:
			#print("different release code word?")
			return 3
		if t0[i].isalpha() and t1[i].isnumeric():
			#print("t0 has code word and t1 doesnt")
			return 3
		if t1[i].isalpha() and t0[i].isnumeric():
			#print("t1 has code word and t0 doesnt")
			return 3


	if len(t0) > len(t1):
		#print("t0 more specific version then t1")
		return 3 # todo: compare release date
	
	if len(t0) < len(t1):
		#print("t0 less specific version then t1")
		return 3 # todo: compare release date

	for i in range(len(t0)):
		if t0[i].isnumeric() and t1[i].isnumeric():
			if int(t0[i]) > int(t1[i]):
				#print("t0 newer then t1")
				return 0
			if int(t0[i]) < int(t1[i]):#
				#print("t0 older then t1")
				return 1	


for fname in glob(composepath):
	data = parse_compose_file(fname)
	for img in data:
		upd = ["Don't update"]
		cur = split_tag(data[img]["current"])
		for tag in data[img]["available"]:
			#print(tag)
			t = list(tag.keys())[0]
			t_sp  = split_tag(t)
			if compare_tags(cur,t_sp) == 1:
				upd.append(t)
		if len(upd) > 1:	
			print("\n"+fname)
			print(f"Update(s) for {img}: {data[img]['current']} ==> {upd}")
			terminal_menu = TerminalMenu(upd)
			menu_entry_index = terminal_menu.show()
			print(f"You have selected: {upd[menu_entry_index]}!")

			if menu_entry_index > 0:
				replaced_content = ""
				with open(fname,"r") as f:
					with open("composefile_backups/"+os.path.basename(fname)+"."+datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S'),'w') as backup:
						backup.write(f.read())
				with open(fname,"r") as f:
					for line in f:
						line = line.strip("\n")
						new_line = line.replace(f"{img.replace('library/','')}:{data[img]['current']}", f"{img.replace('library/','')}:{upd[menu_entry_index]}")
						replaced_content = replaced_content + new_line + "\n"
				with open(fname,"w") as f:
					f.write(replaced_content)

