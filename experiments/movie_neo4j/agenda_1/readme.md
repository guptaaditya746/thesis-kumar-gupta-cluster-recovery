no need for onotology

neo4j introductory 

how to replicate :

just launch the ssh forwarding form proxomox to local

1.     ssh -L 5432:127.0.0.1:5432 \
-L 7474:127.0.0.1:7474 \
-L 7687:127.0.0.1:7687 \
-L 11434:127.0.0.1:11434 \
root@10.247.228.78


2. then open : localhost:7474/
3. movie data is there



## key to note
how to work with neo4j interface
