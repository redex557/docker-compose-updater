from json.decoder import JSONDecodeError
import yaml
import json
import http.client
from glob import glob

arch = "amd64"
splitchars = [".","-","_"]

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


for fname in glob('files/*.yml'):
	print(fname)
	data = parse_compose_file(fname)
	for img in data:
		cur = split_tag(data[img]["current"])
		for tag in data[img]["available"]:
			#print(tag)
			t = list(tag.keys())[0]
			t_sp  = split_tag(t)
			if compare_tags(cur,t_sp) == 1:
				print(img)
				print("Update: ",data[img]["current"],"==>",t,"\n")

