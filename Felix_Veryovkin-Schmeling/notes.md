direct visit to website follows pattern:
"https://{website name and search field}/search/query={blah blah blah etc...}"

gemm4:12b -> num_ctx: 262144, num_thread: 4, num_gpu: 99, temperature: 0.1 num_predict: 65536, stream = True
granite4:350m -> num_ctx: 32768, num_thread: 0, num_gpu: 99, temperature: 0.1, num_predict: 8192, stream = True ***USE FOR TESTING***





##POTENTIALLY USEFUL WEBSITES###
1. https://descriptor-libraries.molssi.org (ligand database has downloadable database(s) as well)
2. https://compbio.sjtu.edu.cn/services/clc-db (has downloadable database(s) as well)
3. https://fluobase.siochemdb.com (additional database)


4. arxiv.org, bioRxiv.org, ChemRxiv.org -> all pre-print libraries of publications
5. 


### Other Things ###

1. For sources such as pdfs maybe use an approach where the pdf is converted into a series of png images that can be read with computer vision??, need to investigate
   other ways to get local LLM to read pdf text directly
2. Need to implement postgresql database and investigate how to add additional data to postgres database, e.g. how to get the text from a pdf into it's own table
   in the postgres database
3. Latex output/input
4. fine tune webscraping based on page screenshots
5. Implement a filtering ai model???
6. 







# Make Final Write-Up pretty, probably just re-write the whole thing #

 - mention fixing of results by changing from dictionary to list
 - 




# *FUTURE IDEAS BRAINSTORMING* #

- maybe move away from web-scraping entirely and store all data locally, e.g. maybe just scrape all desired websites/sources ONCE, save
  the information and create a local database from it??
