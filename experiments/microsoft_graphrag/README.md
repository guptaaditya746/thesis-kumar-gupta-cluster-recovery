### How to run 

in the root repo , microsoft_graphrag/
source .venv/bin/activate


## then run if not already once :

graphrag_index

## then for query

graphrag query "What are the top themes in this story?"

graphrag query \
"Who is Scrooge and what are his main relationships?" \
--method local
