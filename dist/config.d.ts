export declare const config: {
    port: number;
    host: string;
    pythonService: {
        url: string;
        host: string;
        port: number;
    };
    networkIP: string;
    frontendUrl: string;
    cors: {
        origin: boolean;
        credentials: boolean;
        methods: string[];
        allowedHeaders: string[];
        exposedHeaders: string[];
    };
    socketIO: {
        maxHttpBufferSize: number;
        cors: {
            origin: boolean;
            methods: string[];
            credentials: boolean;
            allowedHeaders: string[];
        };
        allowEIO3: boolean;
        transports: string[];
    };
    upload: {
        dest: string;
        maxSize: number;
        allowedMimeTypes: string[];
    };
    isDevelopment: boolean;
    nodeEnv: string;
};
export default config;
//# sourceMappingURL=config.d.ts.map