
###
### IIIF Presentation API version 2 to version 3 upgrader
###

import json
import requests

class Upgrader(object):

	def __init__(self, flags={}):
		self.crawl = flags.get("crawl", False)
		self.description_is_metadata = flags.get("desc_2_md", True)
		self.allow_extensions = flags.get("ext_ok", False)
		self.default_lang = flags.get("default_lang", "@none")
		self.deref_links = flags.get("deref_links", True)


		self.language_properties = ['label', 'attribution', 'summary']

		self.all_properties = [
			"label", "metadata", "summary", "thumbnail", "navDate",
			"attribution", "rights", "logo", "value",
			"id", "type", "format", "language", "profile", "timeMode",
			"height", "width", "duration", "viewingDirection", "behavior",
			"related", "rendering", "service", "seeAlso", "within",
			"start", "includes", "items", "structures", "annotations"]

		self.annotation_properties = [
			"body", "target", "motivation"
		]

		self.set_properties = [
			"thumbnail", "rights", "logo", "behavior",
			"related", "rendering", "service", "seeAlso", "within"
		]

		self.object_property_types = {
			"thumbnail": "Image", 
			"logo":"Image", 
			"related": "", 
			"rendering": "", 
			"service": "Service", 
			"rights": "", 
			"seeAlso": "Dataset", 
			"within": ""
		}

		self.profile_map = {
			"http://library.stanford.edu/iiif/image-api/1.1/conformance.html#level0": "level0",
			"http://library.stanford.edu/iiif/image-api/1.1/conformance.html#level1": "level1",
			"http://library.stanford.edu/iiif/image-api/1.1/conformance.html#level2": "level2",
			"http://iiif.io/api/image/1/level0.json": "level0",
			"http://iiif.io/api/image/1/level1.json": "level1",
			"http://iiif.io/api/image/1/level2.json": "level2",
			"http://iiif.io/api/image/2/level0.json": "level0",
			"http://iiif.io/api/image/2/level1.json": "level1",
			"http://iiif.io/api/image/2/level2.json": "level1",	
			"http://iiif.io/api/auth/1/kiosk": "kiosk",
			"http://iiif.io/api/auth/1/login": "login",
			"http://iiif.io/api/auth/1/clickthrough": "clickthrough",
			"http://iiif.io/api/auth/1/external": "external"	
		}
		
		self.content_type_map = {
			"image": "Image",
			"audio": "Sound",
			"video": "Video",
			"application/pdf": "Text",
			"text/html": "Text",
			"text/plain": "Text",
			"application/xml": "Dataset",
			"text/xml": "Dataset"
		}

		#'full': 'source',
		#'style': 'styleClass'


	def retrieve_resource(self, uri):
		resp = requests.get(uri)
		return resp.json()

	def traverse(self, what):
		new = {}
		for (k,v) in what.items():
			if k in self.language_properties:
				new[k] = v
				continue
			elif k == 'metadata':
				# also handled by language_map
				new[k] = v
				continue
			elif k == 'structures':
				# processed by Manifest directly to unflatten
				new[k] = v
				continue
			if type(v) == dict:
				new[k] = self.process_resource(v)
			elif type(v) == list:
				newl = []
				for i in v:
					if type(i) == dict:
						newl.append(self.process_resource(i))
					else:
						newl.append(i)
				new[k] = newl
			else:
				new[k] = v
			if not k in self.all_properties and not k in self.annotation_properties:
				print "Unknown property: %s" % k

		return new

	def fix_service_type(self, what):
		# manage known service contexts
		# assumes an answer to https://github.com/IIIF/api/issues/1352
		if '@context' in what:
			ctxt = what['@context']
			if ctxt == "http://iiif.io/api/image/2/context.json":
				what['type'] = "ImageService2"
				del what['@context']
				return what				
			elif ctxt == "http://iiif.io/api/image/1/context.json":
				what['type'] = "ImageService1"			
				del what['@context']
				return what
			elif ctxt in ["http://iiif.io/api/search/1/context.json",
				"http://iiif.io/api/auth/1/context.json"]:
				# handle below in profiles
				pass
			else:
				print "Unknown context: %s" % ctxt

		if 'profile' in what:
			# Auth: CookieService1 , TokenService1
			p = what['profile']
			if profile in [
				"http://iiif.io/api/auth/1/kiosk",
				"http://iiif.io/api/auth/1/login",
				"http://iiif.io/api/auth/1/clickthrough",
				"http://iiif.io/api/auth/1/external"]:
				what['type'] = 'AuthCookieService1'
			elif profile == "http://iiif.io/api/auth/1/token":
				what['type'] = 'AuthTokenService1'
			elif profile == "http://iiif.io/api/search/1/search":
				what['type'] = "SearchService1"
			elif profile == "http://iiif.io/api/search/1/autocomplete":
				what['type'] = "AutoCompleteService1"
		return what

	def fix_type(self, what):
		# Called from process_resource so we can switch
		t = what.get('@type', '')
		if t:
			if t.startswith('sc:'):
				t = t.replace('sc:', '')
			elif t.startswith('oa:'):
				t = t.replace('oa:', '')
			elif t.startswith('dctypes:'):
				t = t.replace('dctypes:', '')
			if t == "Layer":
				t = "AnnotationCollection"
			elif t == "AnnotationList":
				t = "AnnotationPage"
			what['type'] = t
			del what['@type']
		else:
			# Upgrade service types based on contexts & profiles
			what = self.fix_service_type(what)
		return what

	def do_language_map(self, value):
		new = {}
		defl = self.default_lang
		if type(value) == unicode:
			new[defl] = [value]
		elif type(value) == dict:
			try:
				new[value['@language']].append(value['@value'])
			except:
				new[value['@language']] = [value['@value']]
		elif type(value) == list:
			for i in value:
				if type(i) == unicode:
					try:
						new[defl].append(i)
					except:
						new[defl] = [i]
				elif type(i) == dict:
					try:
						new[i['@language']].append(i['@value'])
					except:
						new[i['@language']] = [i['@value']]
		return new


	def fix_languages(self, what):
		for p in self.language_properties:
			if p in what:
				try:
					what[p] = self.do_language_map(what[p])
				except:
					print what
					raise
		if 'metadata' in what:
			newmd = []
			for pair in what['metadata']:
				l = self.do_language_map(pair['label'])
				v = self.do_language_map(pair['value'])
				newmd.append({'label': l, 'value': v})
			what['metadata'] = newmd
		return what

	def fix_sets(self, what):
		for p in self.set_properties:
			if p in what:
				v = what[p]
				if type(v) != list:
					v = [v]
				what[p] = v
		return what

	def fix_objects(self, what):
		for (p,typ) in self.object_property_types.items():
			if p in what:
				new = []
				for v in what[p]:
					if not type(v) == dict:
						v = {'id':v}
					if not 'type' in v and typ:
						v['type'] = typ
					elif self.deref_links:
						# do a HEAD on the resource and look at Content-Type
						try:
							h = requests.head(v['id'])
						except:
							# dummy URI
							h = None
						if h and h.status_code == 200:
							ct = h.headers['content-type']
							ct = ct.lower()
							first = ct.split('/')[0]

							if first in self.content_type_map:
								v['type'] = self.content_type_map[first]
							elif ct in self.content_type_map:
								v['type'] = self.content_type_map[ct]
							elif ct.startswith("application/json") or \
								ct.startswith("application/ld+json"):
								# Try and fetch and look for a type!
								fh = requests.get(v['id'])
								data = fh.json()
								if 'type' in data:
									v['type'] = data['type']
								elif '@type' in data:
									data = self.fix_type(data)
									v['type'] = data['type']

						if not 'type' in v:
							print "Don't know type for %s: %s" % (p, what[p])
					new.append(v)
				what[p] = new
		return what

	def process_generic(self, what):
		if '@id' in what:
			what['id'] = what['@id']
			del what['@id']
		# @type already processed
		if 'license' in what:
			what['rights'] = what['license']
			del what['license']
		if 'viewingHint' in what:
			what['behavior'] = what['viewingHint']
			del what['viewingHint']
		if 'description' in what:
			if self.description_is_metadata:
				# Put it in metadata
				md = what.get('metadata', [])
				# NB this must happen before fix_languages
				md.append({"label": u"Description", "value": what['description']})
				what['metadata'] = md
			else:
				# rename to summary
				what['summary'] = what['description']
			del what['description']

		if "profile" in what:
			p = what['profile']
			if p in self.profile_map:
				what['profile'] = self.profile_map[p]
			else:
				print "Unrecognized profile: %s (continuing)" % p

		what = self.fix_languages(what)
		what = self.fix_sets(what)
		what = self.fix_objects(what)

		return what

	def process_collection(self, what):
		what = self.process_generic(what)

		nl = []
		colls = what.get('collections', [])
		for c in colls:
			if not type(c) == dict:
				c = {'id': c, 'type': 'Collection'}
			elif not 'type' in c:
				c['type'] = 'Collection'
			nl.append(c)
		mfsts = what.get('manifests', [])		
		for m in mfsts:
			if not type(m) == dict:
				m = {'id': m, 'type': 'Manifest'}
			elif not 'type' in m:
				m['type'] = 'Manifest'
			nl.append(m)			
		members = what.get('members', [])
		nl.extend(members)

		if nl:
			what['items'] = nl
		if mfsts:
			del what['manifests']
		if colls:
			del what['collections']
		if members:
			del what['members']

		return what

	def process_manifest(self, what):
		what = self.process_generic(what)

		if 'startCanvas' in what:
			v = what['startCanvas']
			if type(v) != dict:
				what['start'] = {'id': v, 'type': "Canvas"}
			else:
				v['type'] = "Canvas"
				what['start'] = v
			del what['startCanvas']

		# Need to test as might not be top object
		if 'sequences' in what:
			what['items'] = what['sequences']
			del what['sequences']

		if 'structures' in what:
			# Need to process from here, to have access to all info
			# needed to unflatten them
			rhash = {}
			tops = []
			for r in what['structures']:
				new = self.fix_type(r)
				new = self.process_range(new)				
				rhash[new['id']] = new
				tops.append(new['id'])

			for rng in what['structures']:
				if 'within' in rng:
					tops.remove(rng['id'])
					parid = rng['within'][0]['id']
					del rng['within']
					parent = rhash.get(parid, None)
					if not parent:
						# Just drop it on the floor?
						print "Unknown parent range: %s" % parid
					else:
						# e.g. Harvard has massive duplication of canvases
						# not wrong, but don't need it any more
						for child in rng['items']:
							for sibling in parent['items']:
								if child['id'] == sibling['id']:
									parent['items'].remove(sibling)
									break
						parent['items'].append(rng)
			what['structures'] = []
			for t in tops:
				what['structures'].append(rhash[t])
		return what

	def process_sequence(self, what):
		what = self.process_generic(what)
		what['items'] = what['canvases']
		del what['canvases']

		if 'startCanvas' in what:
			v = what['startCanvas']
			if type(v) != dict:
				what['start'] = {'id': v, 'type': "Canvas"}
			else:
				v['type'] = "Canvas"
				what['start'] = v
			del what['startCanvas']

		return what

	def process_canvas(self, what):
		what = self.process_generic(what)

		newl = {'type': 'AnnotationPage', 'items': []}
		for anno in what['images']:
			newl['items'].append(anno)
		what['items'] = [newl]
		del what['images']

		return what

	def process_annotationpage(self, what):
		what = self.process_generic(what)
		return what

	def process_annotationcollection(self, what):
		what = self.process_generic(what)
		return what

	def process_annotation(self, what):
		what = self.process_generic(what)

		if 'on' in what:
			what['target'] = what['on']
			del what['on']
		if 'resource' in what:
			what['body'] = what['resource']
			del what['resource']

		m = what.get('motivation', '')
		if m:
			if m.startswith('sc:'):
				m = m.replace('sc:', '')
			elif m.startswith('oa:'):
				m = m.replace('oa:', '')
			what['motivation'] = m

		return what

	def process_range(self, what):
		what = self.process_generic(what)

		nl = []
		rngs = what.get('ranges', [])
		for r in rngs:
			if not type(r) == dict:
				r = {'id': r, 'type': 'Range'}
			elif not 'type' in r:
				r['type'] = 'Range'
			nl.append(r)
		cvs = what.get('canvases', [])		
		for c in cvs:
			if not type(c) == dict:
				c = {'id': c, 'type': 'Canvas'}
			elif not 'type' in c:
				c['type'] = 'Canvas'
			nl.append(c)			
		members = what.get('members', [])
		nl.extend(members)

		if rngs:
			del what['ranges']
		if cvs:
			del what['canvases']
		if members:
			del what['members']

		what['items'] = nl

		# contentLayer
		if 'contentLayer' in what:
			v = what['contentLayer']
			if type(v) != dict:
				what['includes'] = {'id': v, 'type': "AnnotationCollection"}
			else:
				v['type'] = "AnnotationCollection"
				what['includes'] = v
			del what['contentLayer']

		# Remove redundant 'top' Range
		if 'behavior' in what and 'top' in what['behavior']:
			what['behavior'].remove('top')

		return what

	def process_choice(self, what):
		what = self.process_generic(what)

		newl = []
		if what.has_key('default'):
			newl.append(what['default'])
			del what['default']
		if what.has_key('item'):
			v = what['item']
			if type(v) != list:
				v = [v]
			newl.extend(v)
			del what['item']
		new['items'] = newl

		return what

	def process_resource(self, what, top=False):

		if top:
			# process @context
			orig_context = what.get("@context", "")
			# could be a list with extensions etc
			del what['@context']

		# First update types, so we can switch on it
		what = self.fix_type(what)
		typ = what.get('type', '')
		if type(typ) == list:
			# Pick one to do first? 
			typ = ""
	
		fn = getattr(self, 'process_%s' % typ.lower(), self.process_generic)

		what = fn(what)
		what = self.traverse(what)

		if top:
			# Add back in the v3 context
			if orig_context != "http://iiif.io/api/presentation/2/context.json":
				# XXX process extensions
				pass
			else:
				what['@context'] = [
    				"http://www.w3.org/ns/anno.jsonld",
    				"http://iiif.io/api/presentation/3/context.json"]

		return what

	def process_uri(self, uri, top=False):
		what = self.retrieve_resource(uri)
		return self.process_resource(what, top)

	def process_cached(self, fn, top=True):
		fh = file(fn)
		data = fh.read()
		fh.close()
		what = json.loads(data)
		return self.process_resource(what, top)


if __name__ == "__main__":

	upgrader = Upgrader(flags={"ext_ok": False, "deref_links": False})

	#results = upgrader.process_cached('/Users/rsanderson/Downloads/harvard_ranges_manifest.json')

	#uri = "http://iiif.io/api/presentation/2.1/example/fixtures/collection.json"
	#uri = "http://iiif.io/api/presentation/2.1/example/fixtures/1/manifest.json"
	#uri = "http://media.nga.gov/public/manifests/nga_highlights.json"
	uri = "https://iiif.lib.harvard.edu/manifests/drs:48309543"
	results = upgrader.process_uri(uri, True)

	print json.dumps(results, indent=2, sort_keys=True)



### TO DO:

### The more complicated stuff

# Determine which annotations should be items and which annotations
# -- this is non trivial, but also not common


### Cardinality Requirements
# Check all presence of all MUSTs in the spec and maybe bail

# A Collection must have at least one label.
# A Manifest must have at least one label.
# An AnnotationCollection must have at least one label.
# id on Collection, Manifest, Canvas, content, Range, 
#    AnnotationCollection, AnnotationPage, Annotation
# type on all
# width+height pair for Canvas, if either
# items all the way down
