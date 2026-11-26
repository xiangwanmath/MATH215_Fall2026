import asyncio
import urllib.parse
import os
import time
import ollama
import re
import random
import torch
import sklearn
import io
import easyocr


from dotenv import load_dotenv

#all the rich. imports are just so the terminal output looks pretty with colors and things
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

#pylatexenc import that allows for conversion of unicode into LaTeX string, which is useful for when the final
# query and data are send to the LLM, so it can understand exactly what functions are being asked about
from pylatexenc.latexwalker  import LatexWalker
from pylatexenc.latex2text import LatexNodes2Text

#playwright headless browser and beautiful soup html parser imports
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

#both googlesearch and ddgs are depracted, as they were web search engines that were replaced by the direct-to-url
# search approach
from ddgs import DDGS


console = Console()

class WebScraper:

    def __init__(self, api_key=None):
        self.api_key = api_key


    def mathjax_to_latex(self, soup):

        if not soup:
            return soup

        for math_script in soup.find_all('script', type=re.compile(r'math/tex')):
            if math_script.string:
                latex_code = math_script.string.strip()
                latex_node = soup.new_string(f"$${latex_code}$$")
                math_script.replace_with(latex_node)

        for annotation in soup.find_all('annotation', encoding=re.compile(r'(?i)application/x-tex')):
            if annotation.text:
                latex_code = annotation.text.strip()
                parent = (annotation.find_parent('mjx-container') or annotation.find_parent('math') or annotation.find_parent('span', class_='MathJax'))
                latex_node = soup.new_string(f"$${latex_code}$$")
                if parent:
                    parent.replace_with(latex_node)
                else:
                    annotation.replace_with(latex_node)

        return soup

    #deprecated html_cleaning function that was used in the search_refinedment file but that file got outdated by the updated direct-to-url search function,
    # html_to_text function will remain in the codebase incase it finds future use
    def html_to_text(self, html_content, url):
        if not html_content:
            return ""

        original_soup = BeautifulSoup(html_content, 'html.parser')

        #removed html tags from text
        for junk in original_soup(["script", "style", "nav", "header", "footer", "form", "noscript", "iframe", "aside"]):
            junk.decompose()

        filtered_soup = self.mathjax_to_latex(original_soup)

        #finding the containers for the desired content
        body =(filtered_soup.find(class_='mt-content-container') or
               filtered_soup.find('main') or
               filtered_soup.find('article') or
               filtered_soup.find(id='main-content') or
               filtered_soup.find(id='mw-content-text'))

        target_node = body if body else filtered_soup

        #image filter that finds images on the webpage and replaces them with their 'alt text' in the scraped result
        for img in target_node.find_all('img',alt = True):
            ocr_payload = img.get('data-ocr-text', '')
            if ocr_payload:
                img.replace_with(f"Image text: {ocr_payload}")
            else:
                img.replace_with(f" {img['alt']}")
        extracted_text = target_node.get_text(separator=' ', strip=True)

        end_page_markers = ["References","See also", "Subject classifications", "Explore with Wolfram|Alpha", "Citations"]
        for marker in end_page_markers:
            if marker in extracted_text:
                extracted_text = extracted_text.split(marker)[0].strip()



        return extracted_text


    #simple matching function that checks if a string contains a given keyword, used in search logic to determine direct search urls based on
    # user query and keyword lists
    def keyword_match_filter(self, keyword, text):
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text))

#deprecated search function that uses google search package, no longer in use due to google web-scraping blockages, is gutted and not complete as it is deprecated
# and was taking up too many lines

    '''def search(self, query, max_results=20, include_domains=None, include_raw_content=True):
        timer_start = time.time()

        console.print(f"[bright_cyan]Querying Google for: {query}[/bright_cyan]")
        results = []

        filtered_search_domains = []
        if include_domains and len(include_domains) >0:
            query_lowercase = query.lower()
            base_urls_of_allowed_domains = [d.replace("https://", "").replace("http://", "").replace("www.", "").strip().lower() for d in include_domains]


            #site filtering using terms


        site_filter_string = f"{' OR '.join([f'site:{d}' for d in filtered_search_domains])}"
        final_query = f"{query} ({site_filter_string})"


        console.print(f"[bright_cyan]Injecting site filters into search: {site_filter_string}[/bright_cyan]")


        encoded_final_query = final_query.replace("(","").replace(")","").replace("?"," ")
        try:
            spoof_query = urllib.parse.quote_plus(encoded_final_query)
            google_search_url = f"https://www.google.com/search?q={spoof_query}"

            console.print("[bright_cyan]Launching headless browser[/bright_cyan]")
            console.print(f"[bright_cyan]Query sent to google:{final_query}[/bright_cyan]")

            # call to playwright headless browser, followed by google search function call (depracted and replaced by direct visit to desired website)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True,args=["--disable-blink-features=AutomationControlled"])
                context = browser.new_context(user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                page = context.new_page()

                time.sleep(random.uniform(0.5, 1.0))

                page.goto(google_search_url, wait_until="domcontentloaded", timeout=10000)

                html_content = page.content()
                context.close()
                browser.close()

                soup = BeautifulSoup(html_content, "html.parser")

                console.print("[bright_cyan]Diagnostics: google results captured[/bright_cyan]")

                result_domain_frequency_tracker = {domain: 0 for domain in filtered_search_domains}
                max_links_per_domain = 2


                for link_tag in soup.find_all("a", href=True):
                    raw_url = link_tag["href"]

                    if "google.com" in raw_url or not raw_url.startswith("http"):
                        continue

                    for domain in filtered_search_domains:
                        if domain in raw_url:

                            if result_domain_frequency_tracker[domain] >= max_links_per_domain:
                                continue


                            if raw_url not in [r["url"] for r in results]:
                                title_tag = link_tag.find("h3")
                                title_text = title_tag.get_text(strip=True) if title_tag else "Source"

                                console.print(f"[bright_cyan]Captured url [{len(results)+1}]: {raw_url}")


                                results.append({
                                    "url": raw_url,
                                    "title": title_text,
                                    "content": ""
                                })

                                result_domain_frequency_tracker[domain] += 1
                                break


                    if len(results) >= max_results:
                        break

        except Exception as e:
            console.print(f"[bright_red]Failed to bypass google firewall with headless browser:{e}")

        console.print(f"[bright_cyan]Web Scraper successful, sending {len(results)} links downstream[/bright_cyan]\n")
        timer_end = time.time() - timer_start
        console.print(f"[deep_pink1]Google search took: {timer_end} seconds [/deep_pink1]")
        return {"results":results[:max_results]}
        '''


    def search(self, query):
        timer_start = time.time()
        query_search = query.lower()
        query = urllib.parse.quote_plus(query)

        #old trusted sources is temp var that will be removed eventually
        '''OLD_trusted_sources = ["mathworld.wolfram.com", "ocw.mit.edu", "proofwiki.org",
                "dlmf.nist.gov", "wikipedia.org",
                "math.libretexts.org", "integral-table.com", "settheory.net","pubchem.ncbi.nlm.nih.gov", "chemistrysteps.com", "ebi.ac.uk", "webqc.org",
                "wikipedia.org", "stenutz.eu", "masterorganicchemistry.com", "jglobal.jst.go.jp",
                "organicchemistrydata.org", "ocw.mit.edu",  "organic-chemistry.org", "chem.libretexts.org", "evans.rc.fas.harvard.edu",
                "chem.rochester.edu","chemspider.com", "chembk.com", "acs.org", "rsc.org",
                "name-reaction.com", "chemistry.msu.edu","webbook.nist.gov"]'''

        #sources_search_urls is the current master-list of all direct-search urls
        sources_search_urls = [f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                                f"https://www.name-reaction.com/{query}",
                                f"https://organicchemistrydata.org/search/?q={query}",
                                f"https://www.masterorganicchemistry.com/?s={query}",
                                f"https://stenutz.eu/chem/search.php?n={query}",
                                f"https://dlmf.nist.gov/search/search?q={query}",
                                f"https://mathworld.wolfram.com/search/?query={query}",
                                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                                f"https://en.wikipedia.org/w/index.php?search={query}&title=Special:Search&ns0=1"]

        #chem_sources and math_sources are work-in-progress compiliations of all all trustworthy sources with websites that make sense and are feasible to use for webscraping,
        # it is worth noting that these variables can and will most likely be expanded and updated in future releases, as they are very lean currently and it takes a considerable
        # amount of time to find 'niche' websites on math and chem and then test them to see if they will fit the usecase of the program
        chem_sources = ["name-reaction.com", "chem.libretexts.org", "organicchemistrydata.org", "masterorganicchemistry.com", "stenutz.eu/chem/search.php", "cssp.chemspider.com"]

        math_sources = ["dlmf.nist.gov", "mathworld.wolfram.com", "math.libretexts.org", "settheory.net"]



        abstract_algebra_and_number_theory_keywords = ["calculate", "formula", "ring", "field", "ideal", "module", "radical", "commutator",
                                                        "solvable group", "abelian", "modulo", "prime", "cryptography",
                                                        "diophantine", "totient", "coprime", "congruence"]

        linear_algebra_and_vector_calculus_keywords =["calculate", "formula", "linear", "variable", "coefficient", "slope", "intercept", "matrix",
                                                        "matrices", "determinant", "vector", "scalar", "eigenvalue", "eigenvector",
                                                        "transpose", "inverse", "dot product", "cross product", "tensor", "basis",
                                                        "dimension", "subspace", "transformation", "gram-schmidt",
                                                        "singular value decomposition", "svd", "qr decomposition", "lu decomposition",
                                                        "hermitian"]

        calculus_and_real_analysis_keywords = ["calculate", "formula", "calculus", "derivative", "integral", "limit", "continuity", "differentiate",
                                                "integrate", "chain rule", "product rule", "quotient rule", "taylor series",
                                                "maclaurin", "differential", "converge", "diverge", "inflection", "concavity",
                                                "maxima", "minima", "l'hopital", "lebesgue", "measure theory", "sequence",
                                                "series", "bernoulli", "infinity"]

        diff_eq_and_math_based_physics_keywords = ["calculate", "formula", "asymptote", "gradient", "hessian", "jacobian", "banach", "hilbert",
                                                    "fourier", "laplace", "sturm-liouville", "wronskian", "bifurcation",
                                                    "attractor", "lipschitz", "sobolev", "dirichlet", "neumann", "cauchy-riemann",
                                                    "residue theorem", "contour integration", "greens function", "partial differential"]

        geometry_and_topology_keywords = ["calculate", "formula", "geometry", "trigonometry", "sine", "cosine", "tangent", "secant",
                                            "cosecant", "cotangent", "angle", "radian", "degree", "triangle",
                                            "circle", "polygon", "sphere", "cylinder", "cone", "volume", "area",
                                            "perimeter", "hypotenuse", "pythagorean", "theorem", "orthogonal",
                                            "parallel", "perpendicular", "radius", "diameter", "circumference"]

        advanced_topology_and_differential_geometry_keywords = ["calculate", "formula", "vertex", "edge", "face", "pi", "homeomorphism", "manifold", "diffeomorphism",
                                                        "homology", "cohomology", "homotopy", "simplicial", "metric space", "hausdorff",
                                                        "compactness", "riemannian", "curvature", "geodesic", "orbifold", "knot theory",
                                                        "affine", "hyperbolic", "parabolic", "elliptic", "topology"]

        statistics_and_probability_keywords = ["calculate", "formula", "statistics", "probability", "mean", "median", "mode", "variance",
                                                "standard deviation", "distribution", "normal distribution", "binomial",
                                                "poisson", "regression", "correlation", "hypothesis", "anova", "chi-square",
                                                "t-test", "p-value", "outlier", "percentile", "quartile", "stochastic",
                                                "percentage"]

        combinatronics_keywords = ["calculate", "formula", "fractal", "mandelbrot", "combinatorics", "combination",
                                                "markov chain", "bayesian", "clt", "central limit theorem", "combinatorial",
                                                "pigeonhole principle", "generating function", "ramsey theory", "graph theory",
                                                "node", "directed graph", "set theory", "union", "intersection", "subset",
                                                "real analysis", "complex analysis", "axiom", "imaginary number", "quaternion",
                                                "boolean", "logic", "proof", "factorial", "bijection", "injection", "surjection",
                                                "poset", "cardinality", "ordinal", "permutation", "unitary", "symmetric", "skew-symmetric",
                                                "lemma", "corollary"]

        general_math_keywords = ["math", "mathematics", "arithmetic", "computation", "algebra", "equation", "function", "proof", "symmetry",
                                 "fraction", "decimal", "ratio", "proportion", "percentage", "absolute value",
                                 "polynomial", "quadratic", "factorization", "logarithm", "exponent", "root", "inequality", "domain", "range",]

        physical_chem_and_quantum_mechanics_keywords = ["quantum", "photon", "spectrum", "absorption", "emission", "spin",
                                                        "configuration", "schrodinger", "hamiltonian", "wavefunction", "hartree-fock",
                                                        "density functional theory", "dft", "hund's rule", "pauli exclusion",
                                                        "heisenberg", "born-oppenheimer", "term symbol", "zeeman effect",
                                                        "effective nuclear charge", "lanthanide contraction", "partition function",
                                                        "hermitian"]

        thermodynamics_and_kinetics_keywords = ["enthalpy", "entropy", "thermodynamics", "kinetics", "equilibrium",
                                        "catalyst", "activation energy", "half-life", "clausius-clapeyron",
                                        "gibbs-duhem", "van 't hoff", "arrhenius", "eyring equation", "fugacity",
                                        "activity coefficient", "exothermic", "endothermic", "pressure",
                                        "temperature", "gas"]

        inorganic_chemistry_keywords = ["ligand", "chelation", "denticity", "organometallic", "crystal field theory",
                                "ligand field theory", "jahn-teller", "backbonding", "hapticity", "metathesis",
                                "zeolites", "spin-crossover", "coordination sphere", "d-d transition",
                                "nephelauxetic", "pi-backbonding", "cisplatin", "ferrocene", "halogen",
                                "noble gas", "alkali", "alkaline"]

        electrochemistry_keywords = ["overpotential", "voltammetry", "impedance", "coulometry", "chemisorption",
                                        "physisorption", "oxidation", "reduction", "redox", "acid", "base", "ph",
                                        "titration", "buffer"]

        general_organic_chemistry_keywords = ["organic", "alkane", "alkene", "alkyne", "alcohol", "ether", "aldehyde",
                                                "ketone", "carboxylic", "ester", "amine", "amide", "aromatic", "benzene",
                                                "polymer", "monomer", "functional group", "bond", "covalent", "ionic",
                                                "metallic", "hydrogen bond", "dipole", "van der waals", "amino acid", "saccharide",
                                                "peptide", "peptide chain", "protein", "monosaccharide", "polysaccharide","carbohydrate",
                                                "lipid", "enzyme", "dna", "rna", "nucleotide", "allosteric", "micelle", "liposome",
                                                "glycolysis", "krebs cycle", "oxidative phosphorylation", "denaturation", "chaperone",
                                                "transcription", "translation", "ribosomal"]

        sterochemistry_keywords = ["london dispersion", "lewis structure", "vsepr", "hybridization", "isomer",
                                    "stereoisomer", "enantiomer", "diastereomer", "chirality", "resonance",
                                    "allotrope", "tautomerism", "carbocation", "carbanion", "carbene",
                                    "nitrene", "epimer", "anomer", "meso compound", "atropisomer", "geometry",
                                    "lattice"]

        reaction_keywords = ["pericyclic", "diels-alder", "aldol", "claisen", "grignard", "sn1", "sn2",
                                "e1", "e2", "snar", "epoxidation", "ozonolysis", "hydrogenation",
                                "retrosynthesis", "syn-addition", "anti-elimination", "regioselectivity",
                                "stereospecificity", "diastereoselective", "nucleophilic", "electrophilic", "product",
                                "mechanism", "reaction", "reactant"]

        lab_methods_keywords = ["laboratory", "flask", "beaker", "pipette", "burette", "chromatography",
                                "spectroscopy", "nmr", "ir", "mass spec", "uv-vis", "distillation",
                                "extraction", "filtration", "crystallization", "centrifuge", "calorimetry",
                                "electrospray", "maldi", "gc-ms", "lc-ms", "hplc", "ftir", "raman", "xps",
                                "auger", "xrd", "sem", "tem", "afm", "coupling constant", "chemical shift",
                                "singlet", "doublet", "triplet", "multiplet", "parts per million", "ppm",
                                "retention factor", "rf value", "western blot", "pcr", "elisa",
                                "electrophoresis", "oligonucleotide", "area", "diameter", "chromatogram",
                                "retention time", "mobile phase", "stationary phase", "beer-lambert law",
                                "molar absorptivity", "monochromator"]

        analytical_chemistry_keywords = ["stoichiometry", "mole", "avogadro", "yield", "hydrolysis",
                                         "combustion", "synthesis", "decomposition", "precipitation", "neutralization","analyte",
                                         "titrant", "equivalence point", "end point", "standardization", "primary standard",
                                         "gravimetry", "gravimetric analysis", "masking agent", "limiting reactant","limiting reagent",
                                         "excess reactant", "theoretical yield", "percent yield", "empirical formula", "molecular formula",
                                         "molar mass", "equivalence factor", "ideal gas law"]

        general_chemistry_keywords = ["chemistry", "chemical", "atom", "molecule", "element", "compound",
                                       "mixture", "solution", "solvent", "solute", "concentration", "molarity",
                                       "molality", "density", "mass", "aqueous","electron", "proton", "neutron",
                                       "nucleus", "orbital", "shell", "valence", "electronegativity", "ionization",
                                       "affinity", "isotope", "ion", "cation", "anion", "plasma", "transition metal",
                                       "lanthanide", "actinide", "metalloid"]


        #hardcoded if/else block that compares query words to hardcoded keyword list and then
        if any(self.keyword_match_filter(i, query_search) for i in abstract_algebra_and_number_theory_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print(f"[bright_green]abstract algebra and number theory[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in linear_algebra_and_vector_calculus_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print("[bright_green]linear algebra and vector calculus[/bright_green]")
        elif any(self.keyword_match_filter(i, query_search) for i in calculus_and_real_analysis_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print(f"[bright_green]calculus and real analysis[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in diff_eq_and_math_based_physics_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print(f"[bright_green]differential equations[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in geometry_and_topology_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print(f"[bright_green]geometry and topology[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in advanced_topology_and_differential_geometry_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print(f"[bright_green]advanced topology and differential geometry[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in statistics_and_probability_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print(f"[bright_green]statistics and probability[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in combinatronics_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki"
            ]
            console.print(f"[bright_green]combinatronics[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in general_math_keywords):
            filtered_search_domains = [
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://en.wikipedia.org/w/index.php?search={query}&title=Special:Search&ns0=1"
            ]
            console.print(f"[bright_green]general mathematics[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in physical_chem_and_quantum_mechanics_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]physical chem[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in thermodynamics_and_kinetics_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]thermodynamics and kinetics[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in inorganic_chemistry_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]inorganic chemistry[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in electrochemistry_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]electrochemistry[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in general_organic_chemistry_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]organic chemistry[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in sterochemistry_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]sterochemistry[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in reaction_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]reactions[/bright_green],, \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in lab_methods_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]lab[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in analytical_chemistry_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}"]
            console.print(f"[bright_green]analytical chemistry[/bright_green], \n {filtered_search_domains}")
        elif any(self.keyword_match_filter(i, query_search) for i in general_chemistry_keywords):
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}",
                f"https://en.wikipedia.org/w/index.php?search={query}&title=Special:Search&ns0=1"]
            console.print("f[bright_green]general chemistry[/bright_green], \n {filtered_search_domains}")
        else:
            filtered_search_domains = [
                f"https://chem.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://www.name-reaction.com/{query}",
                f"https://organicchemistrydata.org/search/?q={query}",
                f"https://www.masterorganicchemistry.com/?s={query}",
                f"https://stenutz.eu/chem/search.php?n={query}",
                f"https://dlmf.nist.gov/search/search?q={query}",
                f"https://mathworld.wolfram.com/search/?query={query}",
                f"https://math.libretexts.org/Special:Search?qid=&fpid=230&fpth=&query={query}&type=wiki",
                f"https://en.wikipedia.org/w/index.php?search={query}&title=Special:Search&ns0=1"
            ]
            console.print(f"[bright_green]other[/bright_green], \n {filtered_search_domains}")



        results = []

        try:
            console.print(f"[bright_cyan] Directly visiting websources for: {query}[/bright_cyan]")

            for url in filtered_search_domains:
                results.append(url)

        except Exception as e:
            console.print(f"[bright_red]Search Error: {e} [/bright_red]")

        timer_end = time.time() - timer_start
        console.print(f"[deep_pink1]Google search took: {timer_end} seconds [/deep_pink1]")
        return results



    def extract(self, urls):
        rendering = Panel.fit(f"[pink] Rendering {len(urls)} urls [/pink]")
        console.print(f"[pink]{rendering}[/pink]")
        results_list = []

        if not hasattr(self, 'ocr_reader'):
            import easyocr
            self.ocr_reader = easyocr.Reader(['en'], gpu=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless = True,
                args=["--disable-blink-features=AutomationControlled", "--window-size=1920,1080"]
            )
            context = browser.new_context(
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )

            for url in urls:
                page = context.new_page()
                try:
                    parsed_url = urllib.parse.urlparse(url)
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    console.print(f"[grey] Rendering content from {base_url} [/grey]")

                    page.goto(url, wait_until='networkidle', timeout = 10000)
                    page.screenshot(path="debugging_screenshot1.png", full_page=True)


                    try:
                        for img_element in page.locator("img").all():
                            box = img_element.bounding_box()
                            ocr_text = ""

                            if box and box['width'] > 50 and box['height'] > 50:
                                img_bytes = img_element.screenshot(timeout=1500)
                                words = self.ocr_reader.readtext(img_bytes)
                                ocr_text = " ".join([w[1] for w in words]).strip()

                            if ocr_text:
                                safe_ocr = ocr_text.replace("'", "\\'").replace('"', '\\"')
                                img_element.evaluate(f"(el) => el.setAttribute('data-ocr-text', '{safe_ocr}')")

                    except Exception as ocr_err:
                        pass


                    html_content = page.content()

                    soup = BeautifulSoup(html_content, 'html.parser')

                    results_list.append({
                        "url":url,
                        "raw_content":html_content
                    })

                except Exception as e:
                    console.print(f"[bright_red] Error, skipped endpoint {url} due to {e}")
                finally:
                    page.close()

            context.close()
            browser.close()

        return {"results": results_list}
