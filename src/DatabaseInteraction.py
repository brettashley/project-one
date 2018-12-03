import psycopg2
import pandas as pd
from psycopg2.extras import Json
from psycopg2 import sql


class DatabaseInteraction():

    def __init__(self, db_name='mixmaker'):
        self.db_name = db_name
        self.conn = psycopg2.connect(dbname=self.db_name, host='localhost')
        self.cur = self.conn.cursor()

    def write_artists(self, artist_urls, return_artist_id=False):
        '''
        Parameters
        ----------
        artists : list of dictionaries

        Returns
        -------
        self :  Writes artist to database
        '''
        for artist in artist_urls:
            if return_artist_id:
                query = """   
                INSERT INTO artists (name, url, scraped)
                SELECT %s, %s, 0
                WHERE %s NOT IN (
                            SELECT url FROM artists
                            )
                RETURNING id;
                
                        """
            else:
                query = """   
                    INSERT INTO artists (name, url, scraped)
                    SELECT %s, %s, 0     
                    WHERE %s NOT IN (
                                SELECT url FROM artists
                                );
                            """
            self.cur.execute(query, (
                 artist["name"],
                 artist["url"],
                 artist["url"]))
            self.conn.commit()

    def write_songs(self, song_urls):
        '''
        Parameters
        ----------
        song_urls : list of dictionaries

        Returns
        -------
        self :  Writes songs to database
        '''
        for song in song_urls:

            if song['artist_id'] is None:

                query = f"""   
                    SELECT id FROM artists
                    WHERE url = %s
                            """
                self.cur.execute(query, (song['artist_url'],))
                self.conn.commit()
                song['artist_id'] = [x for (x,) in self.cur][0]

            query = f"""   
                INSERT INTO songs (artist_id, name, url, scraped)
                SELECT %s, %s, %s, 0
                WHERE %s NOT IN (
                            SELECT url FROM songs
                            );
                        """
            self.cur.execute(query, (
                 song["artist_id"],
                 song["name"],
                 song["url"],
                 song["url"]))
            self.conn.commit()


    def update_scraped_status(self, table, id_to_update, status):
        
        query = """
                UPDATE {}
                SET scraped = %s
                WHERE id = %s
                ;"""

        self.cur.execute(
            sql.SQL(query)
                .format(sql.Identifier(table))
            , (status, id_to_update))
        self.conn.commit()




    def get_next_artist_to_scrape(self):
        """ 
        Returns
        -------
        arist :  dictionary of next artist to scrape      
        """
        query = """
                SELECT id, url, name FROM artists
                WHERE scraped = 0
                ORDER BY id
                LIMIT 1
                """

        self.cur.execute(query)
        self.conn.commit()
        output = list(self.cur)
        return {'id' : output[0][0],
                'url' : output[0][1],
                'name': output[0][2]}

    def get_next_song_to_scrape(self, artist_id=None):
        """ 
        Returns
        -------
        arist :  dictionary of next artist to scrape      
        """
        if artist_id is None:
            query = """
                    SELECT id, url FROM songs
                    WHERE scraped = 0
                    ORDER BY id
                    LIMIT 1
                    """
            self.cur.execute(query)
        
        else:
            query = """
                    SELECT id, url FROM songs
                    WHERE scraped = 0
                    AND artist_id = %s
                    ORDER BY id
                    LIMIT 1
                    """
            self.cur.execute(query, (artist_id,))

        self.conn.commit()
        output = list(self.cur)
        return {'id' : output[0][0],
                'url' : output[0][1]}

    def count_songs_to_scrape(self, artist_id):
        query = """
                SELECT count(*) FROM songs
                WHERE scraped = 0
                AND artist_id = %s
                """

        self.cur.execute(query, (artist_id,))
        self.conn.commit()
        return [x for (x,) in self.cur][0]

    
    def insert_contains_sample(self, song_id, sample_song_id):
        '''
        Parameters
        ----------
        song_urls : list of dictionaries

        Returns
        -------
        self :  Writes songs to database
        '''
        query = f"""   
            INSERT INTO connections (song_id, sampled_by_song_id, is_connected)
            
            SELECT %s, %s, 1
                    
            WHERE (%s, %s) NOT IN (
                        SELECT song_id, sampled_by_song_id FROM connections
                        );
                    """
        self.cur.execute(query, (
                song_id,
                sample_song_id,
                song_id,
                sample_song_id))
        self.conn.commit()

    def get_song_id(self, song_url):
        query = """   
                SELECT id
                FROM songs    
                WHERE url = %s;
                """
        self.cur.execute(query, (song_url,))
        self.conn.commit()
        return [x for (x,) in self.cur][0]

    def get_artist_info(self, artist_id=None, url=None):
        """ 
        Returns
        -------
        arist :  dictionary of desired artist   
        """
        if artist_id is not None:
            query = """
                    SELECT id, url, name, scraped FROM artists
                    WHERE id = %s
                    """
            self.cur.execute(query, (artist_id,))
        elif url is not None:
            query = """
                    SELECT id, url, name, scraped FROM artists
                    WHERE url = %s
                    """
            self.cur.execute(query, (url,))

        self.conn.commit()
        output = list(self.cur)
        return {'id' : output[0][0],
                'url' : output[0][1],
                'name': output[0][2],
                'scraped': output[0][3]}
        
    def get_next_artist_for_spotify(self):
        query = """   
                SELECT a.name, count(s.artist_id) as artist_freq
                FROM artists a
                JOIN songs s
                ON a.id = s.artist_id
                GROUP BY a.id
                HAVING a.scraped_spotify = 0
                ORDER BY artist_freq DESC
                LIMIT 1;
                """
        self.cur.execute(query)
        self.conn.commit()


        def update_scraped_spotify_status(self, table, id_to_update, status):
        
            query = """
                    UPDATE {}
                    SET scraped_spotify = %s
                    WHERE id = %s
                    ;"""

            self.cur.execute(
                sql.SQL(query)
                    .format(sql.Identifier(table))
                , (status, id_to_update))
            self.conn.commit()





